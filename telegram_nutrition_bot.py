import os
import logging
import json
from datetime import datetime, time
import asyncio
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import google.generativeai as genai
import requests
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Set up detailed LLM logging
if not os.path.exists('nutrition_logs'):
    os.makedirs('nutrition_logs')

# Find the next available log number
log_number = 1
while os.path.exists(f'nutrition_logs/nutrition{log_number}.log'):
    log_number += 1

nutrition_log_filename = f'nutrition_logs/nutrition{log_number}.log'
llm_logger = logging.getLogger('NutritionLLMLogger')
llm_logger.setLevel(logging.INFO)

# Set formatter without limiting message length
class FullMessageFormatter(logging.Formatter):
    def formatMessage(self, record):
        return self._style.format(record)

# Handlers setup for LLM logger
llm_file_handler = logging.FileHandler(nutrition_log_filename, encoding='utf-8')
llm_formatter = FullMessageFormatter('%(asctime)s - %(levelname)s - %(message)s')
llm_file_handler.setFormatter(llm_formatter)
llm_logger.addHandler(llm_file_handler)
llm_logger.propagate = False  # Don't send logs to parent logger

# Log the startup
llm_logger.info(f"Starting Nutrition Tracking Bot with LLM log file: {nutrition_log_filename}")

# API keys and configurations
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY")
USDA_API_KEY = os.getenv("USDA_API_KEY", "YOUR_USDA_API_KEY")

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# Storage for daily food entries
# Structure: {user_id: [{meal: "food description", time: timestamp, nutrition: {...}}]}
food_logs = {}

# USDA API endpoint
USDA_API_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"

# Daily nutrition goals for an adult  (simplified)
DAILY_GOALS = {
    "calories": 2000,
    "protein": 50,  # grams
    "carbs": 275,   # grams
    "fat": 70,      # grams
    "fiber": 25,    # grams
    "sugar": 50,    # grams
    "sodium": 1500, # mg
    "calcium": 1000,# mg
    "iron": 18,     # mg
    "vitamin_c": 90,# mg
    "vitamin_a": 900, # mcg
    "water": 3000   # ml
}

# Define path for food log storage
FOOD_LOG_PATH = Path("nutrition_data.json")

# Function to save food logs to file
def save_food_logs():
    try:
        logger.info(f"Saving food logs to {FOOD_LOG_PATH}, current logs: {food_logs.keys()}")
        
        # Convert user IDs to strings for JSON serialization
        json_compatible_logs = {}
        for user_id, logs in food_logs.items():
            # Create JSON-compatible version of the logs
            serializable_logs = []
            for entry in logs:
                # Create a clean copy of each entry
                clean_entry = {
                    "meal": entry.get("meal", ""),
                    "time": entry.get("time", 0),
                    "nutrition": {}
                }
                
                # Copy nutrition data
                if "nutrition" in entry and isinstance(entry["nutrition"], dict):
                    for k, v in entry["nutrition"].items():
                        clean_entry["nutrition"][k] = float(v) if isinstance(v, (int, float)) else 0
                
                serializable_logs.append(clean_entry)
            
            json_compatible_logs[str(user_id)] = serializable_logs
            
        # Debug output
        logger.info(f"Prepared JSON-compatible logs: {list(json_compatible_logs.keys())}")
            
        with open(FOOD_LOG_PATH, 'w') as f:
            json.dump(json_compatible_logs, f)
        logger.info(f"Food logs saved to {FOOD_LOG_PATH}")
    except Exception as e:
        logger.error(f"Error saving food logs: {str(e)}")
        logger.exception("Full traceback:")

# Function to load food logs from file
def load_food_logs():
    if FOOD_LOG_PATH.exists():
        try:
            logger.info(f"Loading food logs from {FOOD_LOG_PATH}")
            with open(FOOD_LOG_PATH, 'r') as f:
                loaded_logs = json.load(f)
                
                # Convert string user IDs back to integers
                for user_id, logs in loaded_logs.items():
                    try:
                        food_logs[int(user_id)] = logs
                    except ValueError:
                        # If user_id can't be converted to int, use as string
                        food_logs[user_id] = logs
                
                logger.info(f"Food logs loaded from {FOOD_LOG_PATH}, users: {list(food_logs.keys())}")
        except Exception as e:
            logger.error(f"Error loading food logs: {str(e)}")
            logger.exception("Full traceback:")

async def extract_food_items(text):
    """Extract food items from natural language text using Gemini."""
    llm_logger.info(f"=== LLM CALL 1: FOOD EXTRACTION ===")
    llm_logger.info(f"User message: {text}")
    
    prompt = f"""
    Extract the food items from this text: "{text}"
    
    Format your response as a JSON list of food items with quantities if mentioned.
    For example: [{{"food": "eggs", "quantity": "2"}}, {{"food": "milk", "quantity": "1 glass"}}]
    
    If no food items are found, return an empty list: []
    """
    
    llm_logger.info(f"Prompt sent to Gemini:\n{prompt}")
    
    try:
        response = model.generate_content(prompt)
        response_text = response.text
        
        llm_logger.info(f"Full Gemini response:\n{response_text}")
        
        # Extract just the JSON part from the response
        json_start = response_text.find('[')
        json_end = response_text.rfind(']') + 1
        
        if json_start >= 0 and json_end > 0:
            json_text = response_text[json_start:json_end]
            food_items = json.loads(json_text)
            llm_logger.info(f"Extracted food items: {food_items}")
            return food_items
        else:
            logger.error(f"Failed to extract JSON from response: {response_text}")
            return []
    
    except Exception as e:
        logger.error(f"Error extracting food items: {str(e)}")
        return []

async def get_nutrition_from_usda(food_item):
    """Get nutrition information from USDA database."""
    try:
        params = {
            "api_key": USDA_API_KEY,
            "query": food_item["food"],
            "dataType": ["Foundation", "SR Legacy", "Survey (FNDDS)"],
            "pageSize": 1
        }
        
        response = requests.get(USDA_API_URL, params=params)
        if response.status_code != 200:
            logger.error(f"USDA API error: {response.status_code}")
            return None
        
        data = response.json()
        
        if not data.get("foods") or len(data["foods"]) == 0:
            logger.warning(f"No food found for {food_item['food']}")
            return None
        
        food_data = data["foods"][0]
        nutrients = food_data.get("foodNutrients", [])
        
        # Extract relevant nutrient information
        nutrition = {
            "calories": 0,
            "protein": 0,
            "carbs": 0,
            "fat": 0,
            "fiber": 0,
            "sodium": 0,
            "sugar": 0
        }
        
        # Map USDA nutrient IDs to our nutrition keys
        nutrient_map = {
            1008: "calories",   # Energy (kcal)
            1003: "protein",    # Protein
            1005: "carbs",      # Carbohydrates
            1004: "fat",        # Total lipid (fat)
            1079: "fiber",      # Fiber
            1093: "sodium",     # Sodium
            2000: "sugar"       # Total sugars
        }
        
        for nutrient in nutrients:
            nutrient_id = nutrient.get("nutrientId")
            if nutrient_id in nutrient_map:
                nutrition[nutrient_map[nutrient_id]] = nutrient.get("value", 0)
        
        # Adjust for quantity if provided
        quantity_str = food_item.get("quantity", "1")
        quantity = 1.0
        is_grams = False
        
        # Check if the quantity is in grams/g
        if "gram" in quantity_str.lower() or "g " in quantity_str.lower() or quantity_str.lower().endswith("g"):
            is_grams = True
            logger.info(f"Detected gram measurement: {quantity_str}")
            
            
            if "gram" in quantity_str.lower() and not any(c.isspace() for c in quantity_str):
                # Extract just the number part from strings like "50grams"
                number_part = ''.join(filter(lambda x: x.isdigit() or x == '.', quantity_str))
                if number_part:
                    try:
                        quantity = float(number_part)
                        logger.info(f"Extracted quantity from '{quantity_str}': {quantity}g")
                    except ValueError:
                        logger.warning(f"Could not parse number from '{quantity_str}'")
                        
        # Attempt to parse quantity from strings like "2", "1 glass", "3 cups", etc.
        try:
            # For spaced formats like "10 grams", get the first part
            if ' ' in quantity_str:
                quantity = float(''.join(filter(lambda x: x.isdigit() or x == '.', quantity_str.split()[0])))
            # For non-spaced formats that were not already handled above
            elif not is_grams or quantity == 1.0:
                quantity = float(''.join(filter(lambda x: x.isdigit() or x == '.', quantity_str)))
        except:
            quantity = 1.0
            
        logger.info(f"Final parsed quantity: {quantity}, is_grams: {is_grams} for '{quantity_str}'")
        
        # Handle gram measurements differently since USDA data is per 100g
        if is_grams:
            # If quantity is in grams, we need to convert from 100g (USDA standard) to the specified amount
            for key in nutrition:
                nutrition[key] = (nutrition[key] * quantity) / 100
        else:
            # For non-gram measurements (e.g., pieces, cups), use the quantity multiplier directly
            for key in nutrition:
                nutrition[key] *= quantity
        
        
        max_reasonable = {
            "calories": 2000,  
            "protein": 100,    
            "carbs": 200,      
            "fat": 150,        
            "fiber": 50,       
            "sodium": 10000,   
            "sugar": 150       
        }
        
        # Check for unreasonable values
        has_unreasonable_values = False
        for key, max_value in max_reasonable.items():
            if nutrition[key] > max_value:
                logger.warning(f"Unreasonable {key} value: {nutrition[key]} for {food_item['food']}, capping at {max_value}")
                nutrition[key] = max_value
                has_unreasonable_values = True
    
        # Debugging
        if has_unreasonable_values:
            logger.warning(f"Found unreasonable nutrition values for: {food_item['quantity']} {food_item['food']}")
            logger.warning(f"Parsed quantity: {quantity}, is_grams: {is_grams}")
            logger.warning(f"Capped nutrition values: {nutrition}")
        
        return nutrition
    
    except Exception as e:
        logger.error(f"Error getting nutrition from USDA: {str(e)}")
        return None

async def estimate_nutrition_with_llm(food_item):
    """Estimate nutrition using LLM when USDA lookup fails."""
    llm_logger.info(f"=== LLM CALL 2: NUTRITION ESTIMATION ===")
    llm_logger.info(f"Food item: {food_item}")
    
    prompt = f"""
    Estimate the nutritional content for: {food_item['quantity'] if 'quantity' in food_item else '1'} {food_item['food']}
    
    Provide a JSON object with these nutritional values:
    - calories (kcal)
    - protein (g)
    - carbs (g)
    - fat (g)
    - fiber (g)
    - sodium (mg)
    - sugar (g)
    
    Format: {{"calories": 240, "protein": 12, "carbs": 30, "fat": 8, "fiber": 3, "sodium": 400, "sugar": 5}}
    
    Be as accurate as possible with your estimation.
    """
    
    llm_logger.info(f"Prompt sent to Gemini:\n{prompt}")
    
    try:
        response = model.generate_content(prompt)
        response_text = response.text
        
        llm_logger.info(f"Full Gemini response:\n{response_text}")
        
        # Extract just the JSON part from the response
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        
        if json_start >= 0 and json_end > 0:
            json_text = response_text[json_start:json_end]
            nutrition = json.loads(json_text)
            
            # Add validation for unreasonable values from LLM
            # These are per-item maximum reasonable values
            max_reasonable = {
                "calories": 2000,  
                "protein": 100,    
                "carbs": 200,      
                "fat": 150,        
                "fiber": 50,       
                "sodium": 10000,   
                "sugar": 150       
            }
            
            # Check for unreasonable values
            has_unreasonable_values = False
            for key, max_value in max_reasonable.items():
                if key in nutrition and nutrition[key] > max_value:
                    logger.warning(f"Unreasonable {key} value from LLM: {nutrition[key]} for {food_item['food']}, capping at {max_value}")
                    nutrition[key] = max_value
                    has_unreasonable_values = True
            
            # If we found unreasonable values, log this for debugging
            if has_unreasonable_values:
                logger.warning(f"Found unreasonable LLM nutrition values for: {food_item['quantity'] if 'quantity' in food_item else '1'} {food_item['food']}")
                logger.warning(f"Capped nutrition values: {nutrition}")
            
            llm_logger.info(f"Final nutrition estimation: {nutrition}")
            return nutrition
        else:
            logger.error(f"Failed to extract JSON from response: {response_text}")
            return None
    
    except Exception as e:
        logger.error(f"Error estimating nutrition with LLM: {str(e)}")
        return None

async def get_nutrition_hybrid(food_items):
    """Get nutrition info using hybrid approach (USDA + LLM)."""
    results = []
    
    for item in food_items:
        # First try USDA
        nutrition = await get_nutrition_from_usda(item)
        
        # If USDA fails, use LLM
        if not nutrition:
            nutrition = await estimate_nutrition_with_llm(item)
        
        if nutrition:
            results.append({
                "food": item,
                "nutrition": nutrition
            })
    
    return results

async def generate_meal_response(food_items_with_nutrition):
    """Generate a response summarizing the nutritional value of the meal."""
    if not food_items_with_nutrition:
        return "I couldn't identify any food items in your message."
    
    total_nutrition = {
        "calories": 0,
        "protein": 0,
        "carbs": 0,
        "fat": 0,
        "fiber": 0,
        "sodium": 0,
        "sugar": 0
    }
    
    # Calculate total nutrition
    for item in food_items_with_nutrition:
        nutrition = item["nutrition"]
        for key in total_nutrition:
            if key in nutrition:
                total_nutrition[key] += nutrition[key]
    
    # Generate the response
    response = "📊 *Nutritional analysis of your meal:*\n\n"
    
    # List the foods
    response += "*Foods:*\n"
    for item in food_items_with_nutrition:
        quantity = item["food"].get("quantity", "1")
        food = item["food"]["food"]
        response += f"• {quantity} {food}\n"
    
    response += "\n*Nutrition Summary:*\n"
    response += f"• Calories: {round(total_nutrition['calories'])} kcal\n"
    response += f"• Protein: {round(total_nutrition['protein'], 1)}g\n"
    response += f"• Carbs: {round(total_nutrition['carbs'], 1)}g\n"
    response += f"• Fat: {round(total_nutrition['fat'], 1)}g\n"
    response += f"• Fiber: {round(total_nutrition['fiber'], 1)}g\n"
    response += f"• Sugar: {round(total_nutrition['sugar'], 1)}g\n"
    response += f"• Sodium: {round(total_nutrition['sodium'])}mg\n"
    
    return response

async def generate_daily_summary(user_id):
    """Generate a daily summary of nutrition intake."""
    if user_id not in food_logs or not food_logs[user_id]:
        return "You haven't logged any food today."
    
    # Calculate total nutrition for the day
    total_nutrition = {
        "calories": 0,
        "protein": 0,
        "carbs": 0,
        "fat": 0,
        "fiber": 0,
        "sodium": 0,
        "sugar": 0
    }
    
    # List of all foods eaten
    all_foods = []
    
    for entry in food_logs[user_id]:
        nutrition = entry.get("nutrition", {})
        for key in total_nutrition:
            if key in nutrition:
                total_nutrition[key] += nutrition[key]
        
        # Add to foods list
        food_desc = entry.get("meal", "Unknown food")
        all_foods.append(food_desc)
    
    # Calculate percentage of daily goals
    percentages = {}
    for key in total_nutrition:
        if key in DAILY_GOALS and DAILY_GOALS[key] > 0:
            percentages[key] = (total_nutrition[key] / DAILY_GOALS[key]) * 100
    
    # Get today's date in a standard format
    today_date = datetime.now().strftime("%B %d, %Y")
    
    llm_logger.info(f"=== LLM CALL 3: DAILY SUMMARY GENERATION ===")
    llm_logger.info(f"Foods logged: {all_foods}")
    llm_logger.info(f"Total nutrition: {total_nutrition}")
    
    # Create a more detailed prompt for recommendations
    recommendation_prompt = f"""
    Based on this user's food intake for today:
    {", ".join(all_foods)}
    
    Total Nutrition:
    - Calories: {total_nutrition['calories']} kcal (Goal: {DAILY_GOALS['calories']} kcal)
    - Protein: {total_nutrition['protein']}g (Goal: {DAILY_GOALS['protein']}g)
    - Carbs: {total_nutrition['carbs']}g (Goal: {DAILY_GOALS['carbs']}g)
    - Fat: {total_nutrition['fat']}g (Goal: {DAILY_GOALS['fat']}g)
    - Fiber: {total_nutrition['fiber']}g (Goal: {DAILY_GOALS['fiber']}g)
    - Sugar: {total_nutrition['sugar']}g (Goal: {DAILY_GOALS['sugar']}g)
    - Sodium: {total_nutrition['sodium']}mg (Goal: {DAILY_GOALS['sodium']}mg)
    
    Create a detailed nutrition assessment with these sections:
    
    1. Significant Nutrient Discrepancies:
    - For each nutrient that exceeds or falls below goals by more than 10%, calculate the exact percentage difference
    - Format as: "Nutrient: You consumed Xg, which is Y% over/under your goal of Zg"
    
    2. Positive Nutrition Choices:
    - Identify any healthy foods the user consumed
    - Acknowledge good nutrition choices if present
    
    3. Recommendations for Tomorrow:
    - Provide 3-4 specific, actionable recommendations
    - Include specific food alternatives
    - Suggest portion control strategies if calorie goal was exceeded
    - Recommend specific foods to address nutrient deficiencies
    
    Make all recommendations specific, personalized to the foods they actually ate, and actionable.
    """
    
    llm_logger.info(f"Prompt sent to Gemini:\n{recommendation_prompt}")
    
    try:
        response = model.generate_content(recommendation_prompt)
        llm_summary = response.text
        
        llm_logger.info(f"Full Gemini response:\n{llm_summary}")
        
        # Construct the final summary
        summary = "🍽️ *YOUR DAILY NUTRITION SUMMARY* 🍽️\n\n"
        summary += "*Foods logged today:*\n"
        for i, food in enumerate(all_foods):
            summary += f"{i+1}. {food}\n"
        
        summary += "\n*Nutrition Totals:*\n"
        summary += f"• Calories: {round(total_nutrition['calories'])} kcal ({round(percentages.get('calories', 0))}% of goal)\n"
        summary += f"• Protein: {round(total_nutrition['protein'], 1)}g ({round(percentages.get('protein', 0))}% of goal)\n"
        summary += f"• Carbs: {round(total_nutrition['carbs'], 1)}g ({round(percentages.get('carbs', 0))}% of goal)\n"
        summary += f"• Fat: {round(total_nutrition['fat'], 1)}g ({round(percentages.get('fat', 0))}% of goal)\n"
        summary += f"• Fiber: {round(total_nutrition['fiber'], 1)}g ({round(percentages.get('fiber', 0))}% of goal)\n"
        summary += f"• Sugar: {round(total_nutrition['sugar'], 1)}g ({round(percentages.get('sugar', 0))}% of goal)\n"
        summary += f"• Sodium: {round(total_nutrition['sodium'])}mg ({round(percentages.get('sodium', 0))}% of goal)\n"
        
        summary += "\n*Analysis & Recommendations:*\n"
        summary += llm_summary
        
        llm_logger.info(f"Final formatted summary for user:\n{summary}")
        return summary
    
    except Exception as e:
        logger.error(f"Error generating daily summary: {str(e)}")
        return "Sorry, I couldn't generate your daily summary due to an error."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_text(
        f"Hi {user.first_name}! I'm your nutrition tracking bot.\n\n"
        "Simply tell me what you've eaten, and I'll analyze its nutritional content.\n"
        "For example: 'I had 2 eggs and a slice of toast for breakfast'\n\n"
        "I'll send you a daily summary at 8:30 PM.\n\n"
        "Use /summary to see your nutrition summary so far today."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text(
        "How to use this bot:\n\n"
        "1. Tell me what you've eaten\n"
        "   Example: 'I had a chicken sandwich and apple juice'\n\n"
        "2. I'll analyze it and tell you the nutritional content\n\n"
        "3. At 8:30 PM, I'll send you a daily summary\n\n"
        "Commands:\n"
        "/summary - Get your nutrition summary for today\n"
        "/reset - Reset your food log for today\n"
        "/start - Start the bot\n"
        "/help - Show this help message"
    )

async def summary_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a nutrition summary when the command /summary is issued."""
    user_id = update.effective_user.id
    summary = await generate_daily_summary(user_id)
    
    # Save food logs to file after generating summary
    save_food_logs()
    
    # Try to send with Markdown first
    try:
        await update.message.reply_text(summary, parse_mode='Markdown')
    except Exception as e:
        # If Markdown parsing fails, try to send without formatting
        logger.error(f"Error sending summary with Markdown: {str(e)}")
        # Remove potentially problematic Markdown
        cleaned_summary = summary.replace('*', '').replace('_', '')
        await update.message.reply_text(
            "There was an issue with formatting. Here's your summary:\n\n" + cleaned_summary
        )

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reset the food log when the command /reset is issued."""
    user_id = update.effective_user.id
    if user_id in food_logs:
        food_logs[user_id] = []
        
    # Save the empty food logs to file
    save_food_logs()
    
    await update.message.reply_text("Your food log has been reset for today.")

async def process_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process incoming messages about food."""
    user_id = update.effective_user.id
    text = update.message.text
    
    # Initialize user's food log if it doesn't exist
    if user_id not in food_logs:
        food_logs[user_id] = []
    
    # Send "typing" action
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    # Extract food items from the message
    food_items = await extract_food_items(text)
    
    if not food_items:
        await update.message.reply_text("I couldn't identify any food items in your message. Try describing what you ate more specifically.")
        return
    
    # Get nutrition information for each food item
    food_with_nutrition = await get_nutrition_hybrid(food_items)
    
    if not food_with_nutrition:
        await update.message.reply_text("I couldn't find nutritional information for the food you mentioned.")
        return
    
    # Generate response
    response = await generate_meal_response(food_with_nutrition)
    
    # Calculate total nutrition for this meal
    total_nutrition = {
        "calories": 0,
        "protein": 0,
        "carbs": 0,
        "fat": 0,
        "fiber": 0,
        "sodium": 0,
        "sugar": 0
    }
    
    for item in food_with_nutrition:
        nutrition = item["nutrition"]
        for key in total_nutrition:
            if key in nutrition:
                total_nutrition[key] += nutrition[key]
    
    # Store the meal in the user's food log
    food_description = ", ".join([f"{item['food'].get('quantity', '1')} {item['food']['food']}" for item in food_with_nutrition])
    food_logs[user_id].append({
        "meal": food_description,
        "time": datetime.now().timestamp(),
        "nutrition": total_nutrition
    })
    
    # Save food logs to file for the Chrome extension
    save_food_logs()
    
    # Send the response
    await update.message.reply_text(response, parse_mode='Markdown')

def main() -> None:
    """Start the bot."""
    # Load existing food logs if available
    load_food_logs()
    
    # Create the Application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("summary", summary_command))
    application.add_handler(CommandHandler("reset", reset_command))
    
    # Add message handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_message))
    
    # Start the Bot
    application.run_polling()

if __name__ == "__main__":
    main() 