from fastapi import FastAPI, UploadFile, File, HTTPException, Query, Form, Request
from fastapi.middleware.cors import CORSMiddleware
import requests
from PIL import Image
import io
import logging
import time
from datetime import datetime
import google.generativeai as genai
import base64
import json
import telegram
import asyncio
import os
from pathlib import Path

app = FastAPI()

# CORS setup - MUST BE BEFORE ROUTES
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*", "chrome-extension://*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set up logging with high maximum message size
if not os.path.exists('demo_logs'):
    os.makedirs('demo_logs')

# Find the next available demo log number
log_number = 1
while os.path.exists(f'demo_logs/demo{log_number}.log'):
    log_number += 1

log_filename = f'demo_logs/demo{log_number}.log'
logger = logging.getLogger('LLMLogger')
logger.setLevel(logging.INFO)

# Set formatter without limiting message length
class FullMessageFormatter(logging.Formatter):
    def formatMessage(self, record):
        return self._style.format(record)

# Handlers setup
file_handler = logging.FileHandler(log_filename, encoding='utf-8')
console_handler = logging.StreamHandler()
formatter = FullMessageFormatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Ensure logs are written immediately
logger.info(f"Starting Recipe Analyzer API with log file: {log_filename}")

# API configuration
HUGGING_FACE_API_KEY = "" #Replace with your own key
VISION_API_URL = "https://api-inference.huggingface.co/models/Salesforce/blip-image-captioning-large"
HF_HEADERS = {"Authorization": f"Bearer {HUGGING_FACE_API_KEY}"}

# Gemini API configuration
GEMINI_API_KEY = "" #Replace with your own key
genai.configure(api_key=GEMINI_API_KEY)

# Setup Gemini models
vision_text_model = genai.GenerativeModel('gemini-1.5-flash')
text_model_1 = genai.GenerativeModel('gemini-1.5-flash')
text_model_2 = genai.GenerativeModel('gemini-1.5-flash')

# Telegram Bot configuration
TELEGRAM_BOT_TOKEN = "" #Replace with your own token
TELEGRAM_CHAT_ID = "" #Replace with your own chat ID
bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)

# Define path for food log storage
FOOD_LOG_PATH = Path("nutrition_data.json")

# Try to load existing nutrition data
def load_nutrition_data():
    if FOOD_LOG_PATH.exists():
        try:
            with open(FOOD_LOG_PATH, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading nutrition data: {str(e)}")
    return {}

# Save nutrition data to file
def save_nutrition_data(data):
    try:
        with open(FOOD_LOG_PATH, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        logger.error(f"Error saving nutrition data: {str(e)}")

# Import the telegram bot's food logs if available
try:
    from telegram_nutrition_bot import food_logs, generate_daily_summary, DAILY_GOALS
    TELEGRAM_BOT_AVAILABLE = True
    
    # Create a mechanism to export food logs from Telegram bot
    def export_food_logs():
        if not food_logs:
            return {}
        return food_logs
        
    # Add a save_hook to the telegram bot's food_logs
    def save_logs_hook():
        logger.info("Saving nutrition data to file...")
        save_nutrition_data(food_logs)
        
except ImportError:
    TELEGRAM_BOT_AVAILABLE = False
    food_logs = load_nutrition_data()
    
    # Define DAILY_GOALS here as a fallback
    DAILY_GOALS = {
        "calories": 2000,
        "protein": 50,  # grams
        "carbs": 275,   # grams
        "fat": 70,      # grams
        "fiber": 25,    # grams
        "sugar": 50,    # grams
        "sodium": 1500, # mg
    }
    
    def export_food_logs():
        return load_nutrition_data()
        
    def save_logs_hook():
        pass

# Create a helper function for sending Telegram messages
async def send_telegram_file(file_bytes, filename, caption):
    """Send file to Telegram"""
    logger.info("Sending file to Telegram")
    try:
        file_io = io.BytesIO(file_bytes)
        file_io.name = filename
        
        await bot.send_document(
            chat_id=TELEGRAM_CHAT_ID,
            document=file_io,
            caption=caption,
            parse_mode='Markdown'
        )
        logger.info("File sent successfully to Telegram")
        return True
    except Exception as e:
        logger.error(f"Error sending file to Telegram: {str(e)}")
        return False

def encode_image_to_base64(image):
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return img_str

@app.get("/")
async def root():
    return {"message": "Recipe Modifier API is running"}

@app.post("/generate_summary")
async def generate_summary(request: Request):
    try:
        data = await request.json()
        recipe_data = data.get("recipe_data", {})
        
        # Create a focused prompt for the summary
        summary_prompt = f"""Create a summary of this healthy recipe modification, but keep the cooking instructions complete and detailed:

Original Dish: {recipe_data.get('original_analysis', '')}
Dietary Type: {recipe_data.get('dietary_type', '').capitalize()}

Using the recipe analysis and modifications below, create a structured summary:

Recipe Analysis: {recipe_data.get('recipe_analysis', '')}
Modified Recipe: {recipe_data.get('modified_recipe', '')}

Format the response exactly like this:
🍽️ HEALTHY RECIPE MODIFICATION

Original Dish: [name]
Modified Type: [type]

📋 MODIFIED INGREDIENTS
[List the key modified ingredients]

👩‍🍳 COOKING INSTRUCTIONS
[Keep the COMPLETE, DETAILED cooking instructions exactly as provided in the modified recipe. Do not summarize or shorten the cooking steps.]

💪 HEALTH BENEFITS
[Summarize key health benefits]

⏲️ COOKING TIME
[Extract and list prep, cook, and total times]

📊 NUTRITIONAL HIGHLIGHTS
[Summarize key nutritional information]

Keep all cooking instructions detailed and clear. Only summarize the other sections."""

        # Generate summary using Gemini
        summary_response = text_model_1.generate_content(summary_prompt)
        summary = summary_response.text
        
        # Log full summary
        logger.info(f"==== FULL TELEGRAM SUMMARY ====")
        logger.info(f"{summary}")
        
        return {"summary": summary}
    except Exception as e:
        logger.error(f"Error generating summary: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/send_to_telegram")
async def send_to_telegram(request: Request):
    try:
        logger.info("=== Sending recipe to Telegram ===")
        data = await request.json()
        recipe_data = data.get("recipe_data", {})
        
        # First, generate the summary
        try:
            summary_response = await generate_summary(request)
            summary = summary_response.get("summary", "")
        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            summary = "Error generating summary"
        
        try:
            # First send the image if available
            if recipe_data.get("image_base64"):
                image_data = base64.b64decode(recipe_data["image_base64"])
                image_io = io.BytesIO(image_data)
                image_io.name = "food_image.jpg"
                
                await bot.send_photo(
                    chat_id=TELEGRAM_CHAT_ID,
                    photo=image_io,
                    caption="Original Food Image"
                )
            
            # Then send the summary
            await bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=summary,
                parse_mode="Markdown"
            )
            
            logger.info(f"Successfully sent recipe summary to Telegram chat {TELEGRAM_CHAT_ID}")
            return {"success": True, "message": "Recipe sent to Telegram successfully"}
            
        except Exception as e:
            logger.error(f"Telegram error: {str(e)}")
            # Try sending without parse_mode if there was a formatting error
            try:
                await bot.send_message(
                    chat_id=TELEGRAM_CHAT_ID,
                    text=summary
                )
                logger.info(f"Successfully sent plain text recipe to Telegram")
                return {"success": True, "message": "Recipe sent to Telegram successfully (plain text)"}
            except Exception as e2:
                logger.error(f"Second Telegram error: {str(e2)}")
                raise HTTPException(status_code=500, detail=f"Error sending to Telegram: {str(e2)}")
            
    except Exception as e:
        logger.error(f"Error in send_to_telegram: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze_recipe")
async def analyze_recipe(image: UploadFile = File(...), goal: str = Query(None), form_goal: str = None):
    try:
        logger.info(f"=== New Recipe Analysis Started ===")
        # Prioritize query parameter goal over form_data goal
        effective_goal = goal if goal is not None else form_goal
        logger.info(f"Query goal: '{goal}', Form goal: '{form_goal}', Effective goal: '{effective_goal}'")
        
        # Debug string comparison
        valid_goals = ["vegan", "vegetarian", "high-protein", "low-carb"]
        logger.info(f"Valid goals: {valid_goals}")
        
        if effective_goal:
            # Debug character comparison to detect invisible characters or formatting issues
            logger.info(f"Goal characters: {[ord(c) for c in effective_goal]}")
            # Test each valid goal against the input
            for valid_goal in valid_goals:
                logger.info(f"Comparing '{effective_goal}' == '{valid_goal}': {effective_goal == valid_goal}")
        
        if not effective_goal:
            logger.warning(f"Goal is None or empty string")
            effective_goal = "low-carb"
        elif effective_goal not in valid_goals:
            logger.warning(f"Goal '{effective_goal}' not in valid goals list")
            effective_goal = "low-carb"
        else:
            logger.info(f"Using valid dietary goal: '{effective_goal}'")
        
        # Log the final goal being used for processing
        logger.info(f"Final goal being used: '{effective_goal}'")
        
        # From here on, use effective_goal instead of goal
        goal = effective_goal

        # 1. Load and prepare the image
        contents = await image.read()
        img = Image.open(io.BytesIO(contents))
        
        # Convert image to RGB if needed
        if img.mode != 'RGB':
            img = img.convert('RGB')

        # Store base64 image for response
        img_base64 = encode_image_to_base64(img)

        # Method 1: Try vision analysis with Hugging Face first
        try:
            logger.info("Sending image to Hugging Face vision API...")
            img_bytes = io.BytesIO()
            img.save(img_bytes, format='JPEG')
            img_bytes = img_bytes.getvalue()
            
            def make_api_request(url, headers, data, max_retries=3, timeout=30):
                for attempt in range(max_retries):
                    try:
                        response = requests.post(url, headers=headers, data=data, timeout=timeout)
                        if response.status_code == 503:
                            logger.warning(f"Service unavailable (attempt {attempt + 1}/{max_retries}), retrying in 2 seconds...")
                            time.sleep(2)
                            continue
                        return response
                    except Exception as e:
                        if attempt == max_retries - 1:
                            raise e
                        logger.warning(f"Request failed (attempt {attempt + 1}/{max_retries}), retrying in 2 seconds...")
                        time.sleep(2)
                raise HTTPException(status_code=503, detail="Service temporarily unavailable after multiple retries")
            
            vision_response = make_api_request(
                VISION_API_URL,
                HF_HEADERS,
                img_bytes
            )

            if vision_response.status_code == 200:
                dish_analysis = vision_response.json()[0]['generated_text']
                logger.info(f"Vision Analysis from Hugging Face: {dish_analysis}")
            else:
                raise Exception("Hugging Face vision API failed")
        
        # Method 2: If Hugging Face fails, fall back to Gemini Vision
        except Exception as e:
            logger.info(f"Hugging Face vision failed: {str(e)}. Trying Gemini Vision...")
            
            # Use Gemini's vision model to analyze the image
            vision_prompt = "Describe this food image in detail. What dish is shown?"
            vision_response = vision_text_model.generate_content([
                vision_prompt,
                {"mime_type": "image/jpeg", "data": img_bytes}
            ])
            
            # Log full vision response
            logger.info(f"==== VISION RESPONSE FULL TEXT ====")
            logger.info(f"{vision_response.text}")
            
            dish_analysis = vision_response.text
            logger.info(f"Vision Analysis from Gemini: {dish_analysis}")

        # 2. Recipe Analysis using Gemini (first LLM interaction)
        recipe_prompt = f"""Analyze this food item: {dish_analysis}
        
        Please provide a structured analysis with the following sections:
        
        1. Main Ingredients: List the main ingredients visible in this food.
        2. Nutritional Information: Estimate calories, protein, carbs, and fat.
        3. Healthy Alternatives: Suggest healthier substitutes for key ingredients.
        
        Format your response with clear headings and avoid using emoji or special characters.
        Use Markdown for formatting (e.g., ## for headings, * for bullet points).
        Be specific, accurate, and practical in your analysis.
        """

        logger.info(f"Sending recipe analysis prompt to Gemini")
        recipe_response = text_model_1.generate_content(recipe_prompt)
        
        # Log full recipe analysis response
        logger.info(f"==== FULL RECIPE ANALYSIS RESPONSE FROM GEMINI ====")
        logger.info(f"{recipe_response.text}")
        
        recipe_analysis = recipe_response.text
        logger.info(f"Recipe Analysis received from Gemini")

        # 3. Health Modification using Gemini with different context (second LLM interaction)
        # Select the appropriate prompt based on the dietary goal
        logger.info(f"Preparing modification prompt with goal: '{goal}'")
        if goal == "vegan":
            logger.info("Using VEGAN prompt template")
            modification_prompt = f"""Generate a strictly VEGAN version of: {dish_analysis}

You are a vegan chef specializing in homemade recipes. IMPORTANT: ALWAYS create a completely from-scratch recipe. NEVER suggest store-bought alternatives or pre-made products.

Please provide:
1. Alternative Ingredients: 
   - Provide exact measurements for ALL ingredients
   - Use only natural, whole food ingredients
   - Include precise quantities (cups, grams, tablespoons)
   - NO processed or pre-packaged foods allowed

2. Cooking Instructions: 
   - Provide DETAILED step-by-step instructions for making EVERYTHING from scratch
   - Include temperatures, times, and techniques
   - If original is typically store-bought (like ice cream or candy), provide complete homemade method
   - Assume the person has basic kitchen equipment (no specialized machines needed)

3. Health Benefits: 
   - Focus on the benefits of homemade vs store-bought
   - Explain why your substitutions are healthier
   - Mention nutritional benefits of key ingredients

4. Cooking Timeline: Provide estimated preparation time and cooking time in minutes.

Format your response with clear headings and avoid using emoji or special characters.
Use Markdown for formatting (e.g., ## for headings, * for bullet points).
The response MUST be fully vegan and made COMPLETELY from scratch - no exceptions.

For the Cooking Timeline section, use this exact format:
"## Cooking Timeline
* Preparation: X minutes
* Cooking: Y minutes
* Total: Z minutes"
"""
            
        elif goal == "vegetarian":
            logger.info("Using VEGETARIAN prompt template")
            modification_prompt = f"""Create a VEGETARIAN version of: {dish_analysis}

You are a vegetarian chef specializing in homemade recipes. IMPORTANT: ALWAYS create a completely from-scratch recipe. NEVER suggest store-bought alternatives or pre-made products.

Please provide:
1. Alternative Ingredients:
   - Provide exact measurements for ALL ingredients 
   - Use only natural ingredients that can be found in most grocery stores
   - Include precise quantities (cups, grams, tablespoons)
   - NO processed or pre-packaged foods allowed

2. Cooking Instructions:
   - Provide DETAILED step-by-step instructions for making EVERYTHING from scratch
   - Include temperatures, times, and techniques
   - If original is typically store-bought (like ice cream or candy), provide complete homemade method
   - Assume the person has basic kitchen equipment (no specialized machines needed)

3. Health Benefits:
   - Focus on the benefits of homemade vs store-bought
   - Explain why your substitutions are healthier
   - Mention nutritional benefits of key ingredients

4. Cooking Timeline: Provide estimated preparation time and cooking time in minutes.

Format your response with clear headings and avoid using emoji or special characters.
Use Markdown for formatting (e.g., ## for headings, * for bullet points).
The response MUST be fully vegetarian and made COMPLETELY from scratch - no exceptions.

For the Cooking Timeline section, use this exact format:
"## Cooking Timeline
* Preparation: X minutes
* Cooking: Y minutes
* Total: Z minutes"
"""
            
        elif goal == "high-protein":
            logger.info("Using HIGH-PROTEIN prompt template")
            modification_prompt = f"""Create a HIGH-PROTEIN version of: {dish_analysis}

You are a high-protein chef specializing in homemade recipes. IMPORTANT: ALWAYS create a completely from-scratch recipe. NEVER suggest store-bought alternatives or pre-made products.

Please provide:
1. Alternative Ingredients:
   - Provide exact measurements for ALL ingredients 
   - Use only natural protein-rich ingredients
   - Include precise quantities (cups, grams, tablespoons)
   - NO processed protein powders, bars, or pre-packaged foods allowed
   - Each serving should contain at least 25g of protein

2. Cooking Instructions:
   - Provide DETAILED step-by-step instructions for making EVERYTHING from scratch
   - Include temperatures, times, and techniques
   - If original is typically store-bought (like ice cream or candy), provide complete homemade method
   - Assume the person has basic kitchen equipment (no specialized machines needed)

3. Health Benefits:
   - Focus on the benefits of homemade vs store-bought
   - Explain why your high-protein substitutions are healthier
   - Mention muscle-building and satiety benefits
   - Include approximate protein content per serving

4. Cooking Timeline: Provide estimated preparation time and cooking time in minutes.

Format your response with clear headings and avoid using emoji or special characters.
Use Markdown for formatting (e.g., ## for headings, * for bullet points).
The recipe MUST be made COMPLETELY from scratch with no pre-packaged ingredients - no exceptions.

For the Cooking Timeline section, use this exact format:
"## Cooking Timeline
* Preparation: X minutes
* Cooking: Y minutes
* Total: Z minutes"
"""
            
        else:  # Default to low-carb
            logger.info(f"Using LOW-CARB prompt template (goal: '{goal}')")
            modification_prompt = f"""Develop a LOW-CARB version of: {dish_analysis}

You are a low-carb chef specializing in homemade recipes. IMPORTANT: ALWAYS create a completely from-scratch recipe. NEVER suggest store-bought alternatives or pre-made products.

Please provide:
1. Alternative Ingredients:
   - Provide exact measurements for ALL ingredients 
   - Use only natural, whole food ingredients that are low in carbs
   - Include precise quantities (cups, grams, tablespoons)
   - NO processed or pre-packaged "low-carb" foods allowed
   - Keep total carbs UNDER 15g per serving

2. Cooking Instructions:
   - Provide DETAILED step-by-step instructions for making EVERYTHING from scratch
   - Include temperatures, times, and techniques
   - If original is typically store-bought (like ice cream or candy), provide complete homemade method
   - Assume the person has basic kitchen equipment (no specialized machines needed)

3. Health Benefits:
   - Focus on the benefits of homemade vs store-bought
   - Explain why your low-carb substitutions are healthier
   - Mention blood sugar management and other low-carb benefits
   - Include carb count per serving

4. Cooking Timeline: Provide estimated preparation time and cooking time in minutes.

Format your response with clear headings and avoid using emoji or special characters.
Use Markdown for formatting (e.g., ## for headings, * for bullet points).
The recipe MUST be made COMPLETELY from scratch with no pre-packaged ingredients - no exceptions.

For the Cooking Timeline section, use this exact format:
"## Cooking Timeline
* Preparation: X minutes
* Cooking: Y minutes
* Total: Z minutes"
"""

        logger.info(f"Sending {goal} modification prompt to Gemini")
        modification_response = text_model_2.generate_content(modification_prompt)
        
        # Log full modification response
        logger.info(f"==== FULL MODIFICATION RESPONSE FROM GEMINI ====")
        logger.info(f"{modification_response.text}")
        
        modified_recipe = modification_response.text
        logger.info(f"Modified Recipe received from Gemini")

        # 4. Flavor Enhancement using Gemini with different context (third LLM interaction)
        flavor_prompt = f"""For this {goal} version of {dish_analysis}, suggest flavor enhancements.
        
        You are a culinary expert focusing on flavor enhancement. Please provide:
        
        1. Spice & Herb Recommendations: List specific spices and herbs that would enhance the flavor.
        2. Sauce or Dressing Ideas: Suggest {goal}-friendly sauces or dressings.
        3. Presentation Tips: How to make this dish visually appealing.
        
        Format your response with clear headings and avoid using emoji or special characters.
        Use Markdown for formatting (e.g., ## for headings, * for bullet points).
        Keep all suggestions aligned with {goal} dietary requirements."""

        logger.info(f"Sending flavor enhancement prompt to Gemini")
        flavor_response = text_model_1.generate_content(flavor_prompt)
        
        # Log full flavor enhancement response
        logger.info(f"==== FULL FLAVOR ENHANCEMENT RESPONSE FROM GEMINI ====")
        logger.info(f"{flavor_response.text}")
        
        flavor_enhancement = flavor_response.text
        logger.info(f"Flavor Enhancement received from Gemini")

        # Before returning the response
        response_data = {
            "original_analysis": dish_analysis,
            "recipe_analysis": recipe_analysis,
            "modified_recipe": modified_recipe,
            "flavor_enhancement": flavor_enhancement,
            "section_titles": {
                "original": "Original Analysis",
                "analysis": "Recipe Analysis",
                "modified": f"{goal.capitalize()} Recipe",
                "flavor": "Flavor Enhancement"
            },
            "dietary_type": goal,
            "image_base64": img_base64
        }
        
        # Log the final response dietary_type
        logger.info(f"Returning response with dietary_type: '{response_data['dietary_type']}'")
        
        return response_data

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/custom_prompt")
async def custom_prompt(
    prompt: str = Form(...), 
    food_description: str = Form(...),
    dietary_type: str = Form(...),
    recipe_analysis: str = Form(...),
    modified_recipe: str = Form(...),
    flavor_enhancement: str = Form(...)
):
    try:
        logger.info(f"=== Custom Prompt Request ===")
        logger.info(f"Prompt: {prompt}")
        logger.info(f"Food: {food_description}")
        logger.info(f"Diet Type: {dietary_type}")
        
        # Create a context-rich prompt for Gemini
        context_prompt = f"""You are a culinary and nutrition expert with comprehensive knowledge about food, including nutrition, recipes, cooking techniques, food history, culture, and dietary preferences.

Current food being analyzed: {food_description}
        
Here's what we know about this specific food item:

===== RECIPE ANALYSIS =====
{recipe_analysis}

===== {dietary_type.upper()} RECIPE =====
{modified_recipe}

===== FLAVOR ENHANCEMENT =====
{flavor_enhancement}

USER QUESTION: {prompt}

Please answer the user's question thoroughly. If the question relates directly to the specific food item being analyzed, use the provided information. If the question is about general food knowledge, cooking techniques, or food history that's not covered in the provided information, feel free to draw upon your broader knowledge to give a complete and accurate answer.

Format your response using markdown for better readability. Be educational and informative.
"""

        # Send to Gemini for processing
        response = text_model_1.generate_content(context_prompt)
        
        # Log a full response
        logger.info(f"Custom prompt full response:")
        logger.info(f"{response.text}")
        
        return {
            "response": response.text
        }

    except Exception as e:
        logger.error(f"Error processing custom prompt: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get_nutrition_summary")
async def get_nutrition_summary():
    """Get nutrition summary from Telegram bot."""
    try:
        # Try to load the latest food logs from file
        stored_logs = load_nutrition_data()
        
        # Check if we have logs from the Telegram bot or stored logs
        if TELEGRAM_BOT_AVAILABLE and food_logs:
            # Export and save logs from Telegram bot
            save_logs_hook()
            user_logs = food_logs
        else:
            # Use logs from storage
            user_logs = stored_logs
        
        # Get the user ID from the request or use a default one
        # In a real app, you would authenticate users properly
        user_id = "604398528"  # Your Telegram chat ID as string
        
        # Check if the user has logged any food today
        if not user_logs or user_id not in user_logs or not user_logs[user_id]:
            return {
                "foods": [],
                "nutrition": {
                    "calories": 0,
                    "protein": 0,
                    "carbs": 0,
                    "fat": 0,
                    "fiber": 0,
                    "sodium": 0,
                    "sugar": 0
                },
                "recommendations": "You haven't logged any food today. Use the Telegram bot to track your meals."
            }
        
        # Prepare the list of foods
        foods = []
        total_nutrition = {
            "calories": 0,
            "protein": 0,
            "carbs": 0,
            "fat": 0,
            "fiber": 0,
            "sodium": 0,
            "sugar": 0
        }
        
        # Sum up nutrition and collect food names
        for entry in user_logs[user_id]:
            foods.append(entry.get("meal", "Unknown food"))
            
            # Sum up nutrition
            nutrition = entry.get("nutrition", {})
            for key in total_nutrition:
                if key in nutrition:
                    total_nutrition[key] += nutrition[key]
        
        # Log LLM call for Chrome extension
        logger.info(f"=== LLM CALL: CHROME EXTENSION NUTRITION SUMMARY ===")
        logger.info(f"Foods logged: {foods}")
        logger.info(f"Total nutrition: {total_nutrition}")
        
        # Generate detailed recommendations using Gemini
        recommendation_prompt = f"""
        Based on this user's food intake for today:
        {", ".join(foods)}
        
        Total Nutrition:
        - Calories: {total_nutrition['calories']} kcal (Goal: {DAILY_GOALS['calories']} kcal)
        - Protein: {total_nutrition['protein']}g (Goal: {DAILY_GOALS['protein']}g)
        - Carbs: {total_nutrition['carbs']}g (Goal: {DAILY_GOALS['carbs']}g)
        - Fat: {total_nutrition['fat']}g (Goal: {DAILY_GOALS['fat']}g)
        - Fiber: {total_nutrition['fiber']}g (Goal: {DAILY_GOALS['fiber']}g)
        - Sugar: {total_nutrition['sugar']}g (Goal: {DAILY_GOALS['sugar']}g)
        - Sodium: {total_nutrition['sodium']}mg (Goal: {DAILY_GOALS['sodium']}mg)
        
        Create a detailed nutrition assessment with these sections:
        
        Significant Nutrient Discrepancies:
        For each nutrient (including sugar) that exceeds or falls below goals by more than 10%, calculate the exact percentage difference.
        Format each nutrient on a new line WITHOUT using markdown, bullets, or asterisks.
        ALWAYS include analysis of sugar content, especially if it's close to or exceeds the daily goal.
        
        Recommendations:
        Provide 3-4 specific, actionable recommendations based on the nutrients that are most out of balance.
        Include specific food alternatives.
        If sugar is high, ALWAYS provide specific recommendations to reduce sugar intake.
        Format each recommendation as a numbered list (1., 2., 3.) WITHOUT using markdown.
        
        The recommendations must be straightforward, plain text only (NO markdown, NO bold, NO asterisks).
        Keep the entire response under 600 characters for display in the Chrome extension.
        """
        
        logger.info(f"Prompt sent to Gemini for Chrome extension:\n{recommendation_prompt}")
        
        try:
            recommendations = "Eat a balanced diet with plenty of fruits, vegetables, lean proteins, and whole grains."
            
            # Only generate detailed recommendations if we have at least one food
            if foods:
                response = text_model_1.generate_content(recommendation_prompt)
                recommendations = response.text
                logger.info(f"Full Gemini response for Chrome extension:\n{recommendations}")
        except Exception as e:
            logger.error(f"Error generating recommendations: {str(e)}")
            recommendations = "Based on your intake today, try to maintain a balanced diet with appropriate portions of protein, carbs, and healthy fats."
        
        return {
            "foods": foods,
            "nutrition": total_nutrition,
            "recommendations": recommendations
        }
        
    except Exception as e:
        logger.error(f"Error getting nutrition summary: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
