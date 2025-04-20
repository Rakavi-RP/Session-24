# Healthy Recipe Modifier & Daily Nutrition Tracker Agentic AI based Chrome Extension

A powerful Chrome extension that analyzes food images and provides healthy recipe alternatives based on different dietary preferences using VLM and LLM. It also does daily nutrition tracking integrated with Telegram

## 🍽️ Features

### Recipe Analysis & Modification
- **Food Image Analysis**: Upload any food image for instant identification and analysis
- **Multiple Dietary Alternatives**: Generate healthier versions tailored to:
  - Low-Carb
  - High-Protein
  - Vegetarian
  - Vegan
- **Detailed Recipe Generation**: Complete from-scratch recipes with:
  - Full ingredient lists with measurements
  - Step-by-step cooking instructions
  - Nutritional information
  - Cooking time estimates
- **Flavor Enhancement**: Get suggestions for spices, herbs, and presentation tips
- **Q&A Functionality**: Ask follow-up questions about the food, recipes, or nutrition
- **Export Options**:
  - Download complete recipe as HTML
  - Send summary to Telegram

### Nutrition Tracking 
- **Telegram Bot Integration**: Track your daily nutrition through natural conversation
- **Hybrid Nutrition Analysis**: Combined approach using USDA database + LLM
- **Real-time Feedback**: Immediate nutritional analysis of logged foods
- **Daily Summaries**: Comprehensive nutrition review with personalized recommendations
- **Chrome Extension Integration**: View your nutrition logs directly in the extension
- **Agentic AI Pattern**: Multiple LLM interactions with persistent context

## 🛠️ Technology Stack

- **Frontend**: Vanilla JavaScript, HTML, CSS
- **Backend**: FastAPI (Python)
- **AI Models**:
  - **Google Gemini 1.5 Flash**: Multimodal model used for both vision and text analysis
  - **Hugging Face Models** (as alternative options):
    - `Salesforce/blip-image-captioning-large`: For vision analysis
    - `google/flan-t5-small`: For text analysis and recipe generation
- **Additional APIs**: 
  - Telegram Bot API (for recipe sharing and nutrition tracking)
  - USDA FoodData Central API (for nutritional information)

## 📋 Requirements

### Backend (Python requirements)
- Python 3.8+
- FastAPI
- Uvicorn
- Pillow (for image processing)
- python-multipart (for handling file uploads)
- google-generativeai (for Gemini API access)
- python-telegram-bot
- Requests
- python-dotenv

### Chrome Extension Requirements
- Chrome browser
- Developer mode enabled for loading unpacked extensions

## 🚀 Installation & Setup

### Backend Setup

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/recipe-modifier.git
   cd recipe-modifier
   ```

2. Install required packages:
   ```
   pip install fastapi uvicorn pillow python-multipart google-generativeai python-telegram-bot[job-queue] requests python-dotenv
   ```

3. Set up API keys in a `.env` file:
   ```
   # Telegram Bot Token
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   
   # Gemini API Key
   GEMINI_API_KEY=your_gemini_api_key
   
   # USDA API Key
   USDA_API_KEY=your_usda_api_key
   
   # Telegram Chat ID
   TELEGRAM_CHAT_ID=your_telegram_chat_id
   ```

4. Start the server:
   ```
   python -m uvicorn main:app --reload
   ```

5. Start the Telegram bot (in a separate terminal):
   ```
   python telegram_nutrition_bot.py
   ```

### Chrome Extension Setup

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable "Developer mode" (toggle in the top-right corner)
3. Click "Load unpacked" and select the `extension` directory
4. Pin the extension to your toolbar for easy access

## 🧩 How It Works

### Recipe Analysis System

#### AI Model Integration

1. **Vision Language Model (VLM) Request**: 
   - When a food image is uploaded, it's sent to the backend where Gemini 1.5 Flash (or alternatively Hugging Face's BLIP model) analyzes the image
   - The VLM identifies the food and generates a detailed description of what's in the image
   - No fine-tuning required - the models use zero-shot learning to identify food items

2. **First LLM Request - Recipe Analysis**:
   - The food description is sent to Gemini 1.5 Flash 
   - The LLM analyzes the food, listing main ingredients, nutritional estimates, and health considerations
   - This creates the "Recipe Analysis" section

3. **Second LLM Request - Recipe Modification**:
   - Using the food analysis, another prompt is sent to the LLM
   - Based on the selected dietary goal (low-carb, high-protein, vegetarian, vegan), the model creates a custom recipe from scratch
   - The prompt specifically requires detailed measurements, cooking instructions, and health benefits

4. **Third LLM Request - Flavor Enhancement**:
   - A separate LLM request generates culinary suggestions to improve the modified recipe
   - This includes spice recommendations, sauce ideas, and presentation tips

5. **Optional LLM Requests - Q&A**:
   - Users can ask custom questions about the food
   - Each question generates a new LLM request with context from previous analyses
   - The model provides personalized answers about nutrition, cooking techniques, or cultural aspects

6. **Final LLM Request - Telegram Summary** (when sharing):
   - When sending to Telegram, an LLM request generates a concise, well-formatted summary
   - This includes only the essential information, optimized for messaging platforms

### Nutrition Tracking System

#### Telegram Bot Integration

1. **Natural Language Food Logging**:
   - Users message the Telegram bot with what they've eaten (e.g., "I had 2 eggs and toast for breakfast")
   - First LLM Request: Gemini extracts food items from natural language
   - The extracted food items are processed using a hybrid approach:
     - First attempt: USDA FoodData Central API lookup for accurate nutritional data
     - Backup: LLM-based estimation when USDA doesn't have the data
   - The bot responds with immediate nutritional analysis of the logged food

2. **Daily Nutrition Summary**:
   - Users can use the `/summary` command at any time to get their daily totals
   - Second LLM Request: Gemini analyzes all foods logged that day
   - The LLM compares intake against recommended daily values
   - It provides personalized recommendations based on nutritional gaps or excesses
   - All context from previous food entries is maintained

3. **Chrome Extension Integration**:
   - The "Track Today's Nutrition" button in the extension connects to the same data
   - The FastAPI server acts as a bridge between the Telegram bot and Chrome extension
   - Food logs are stored in a JSON file that both systems can access
   - Third LLM Request: When retrieving data for the extension, the LLM provides recommendations based on all nutrition context

## 🔄 LLM Request Flow

### Recipe Analysis Flow
1. **Image Upload** → VLM Request → Food Identification
2. **Food Description** → LLM Request 1 → Recipe Analysis  
3. **Recipe + Dietary Goal** → LLM Request 2 → Customized Recipe
4. **Recipe Context** → LLM Request 3 → Flavor Enhancement
5. **User Question** → LLM Request 4+ → Custom Answers (optional)
6. **Complete Data** → LLM Request → Telegram Summary (if shared)

### Nutrition Tracking Flow
1. **Food Message** → LLM Request 1 → Food Item Extraction
2. **Extracted Foods** → USDA API/LLM Request → Nutritional Data
3. **Daily Summary Command** → LLM Request 2 → Analysis & Recommendations
4. **Extension View** → LLM Request 3 → Chrome Extension Display

## 🤖 Agentic AI Implementation

This project demonstrates advanced agentic AI patterns through:

### 1. Multi-Step Reasoning
- **Recipe Analysis**: Identification → Analysis → Modification → Enhancement
- **Nutrition Tracking**: Extraction → Lookup → Analysis → Recommendations

### 2. Tool Integration
- **External API Usage**: USDA FoodData Central, Telegram Bot API
- **Cross-Platform Data Flow**: Data flows between Telegram, FastAPI, and Chrome Extension
- **Hybrid Approach**: Uses both data lookups and generative AI to improve accuracy

### 3. Context Preservation
- **Recipe Flow**: Each LLM call builds on previous steps (identification → analysis → modification)
- **Nutrition Flow**: Food entries accumulate throughout the day with maintained context
- **Knowledge Sharing**: Information flows between different systems (bot → server → extension)

### 4. Agentic Pattern
The project implements the required agentic AI pattern:
```
Query (food image/message) → 
LLM Response (identification/extraction) → 
Tool Call (analysis/lookup) → Tool Result → 
Query (with context) → 
LLM Response (recipe/recommendations) → 
Tool Call (enhancement/summary) → Tool Result → 
Query (user follow-up) → 
LLM Response (personalized answer)
```

## 🙋‍♂️ Usage

### Recipe Analysis
1. Click the extension icon in Chrome
2. Select a dietary goal (Low-Carb, High-Protein, Vegetarian, or Vegan)
3. Upload a food image or drag-and-drop
4. Wait for analysis (typically 5-10 seconds)
5. View the original analysis and modified recipe
6. Ask custom questions using the question box
7. Download complete recipe or send to Telegram

### Nutrition Tracking
1. Find the Telegram bot by username `@pluggin_food_bot` (Healthy-Food)
2. Send messages about what you've eaten (e.g., "I had 2 eggs and toast for breakfast")
3. Receive immediate nutritional analysis
4. Type `/summary` to see your complete daily nutrition summary
5. In the Chrome extension, click "Track Today's Nutrition" to view the same data

## ⚠️ Limitations

- Analysis quality depends on image clarity
- Nutritional estimates are approximations
- Internet connection required for all features
- API rate limits may apply depending on provider
- USDA database might not contain all food items

## 💡 Future Enhancements

### 1. MCP Integration
- Implementing the system with MCP (Model Context Protocol) would allow:
  - Scheduled notifications without requiring always-on servers
  - More efficient context management between multiple LLM calls
  - Better long-term memory for tracking nutrition trends

### 2. Advanced Analysis
- Tracking nutrition across multiple days/weeks
- Visualizing nutrition trends over time
- Suggesting meal plans based on nutritional gaps

### 3. Mobile Integration
- Mobile app version for on-the-go food logging
- Camera integration for real-time food recognition

