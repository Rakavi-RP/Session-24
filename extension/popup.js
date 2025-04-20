document.addEventListener('DOMContentLoaded', function() {
    // Log DOM elements to debug
    console.log("DOM loaded, looking for elements...");
    
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const loading = document.getElementById('loading');
    const result = document.getElementById('result');
    const imagePreview = document.getElementById('imagePreview');
    const exportButton = document.getElementById('exportButton');
    const customPromptSection = document.getElementById('customPromptSection');
    const customPromptInput = document.getElementById('customPrompt');
    const askButton = document.getElementById('askButton');
    const customResponses = document.getElementById('customResponses');
    
    // New elements for PDF and Telegram
    const actionButtons = document.getElementById('actionButtons');
    const downloadButton = document.getElementById('downloadButton');
    const telegramButton = document.getElementById('telegramButton');
    const toast = document.getElementById('toast');

    // New elements for nutrition tracking
    const trackNutritionButton = document.getElementById('trackNutritionButton');
    const nutritionModal = document.getElementById('nutritionModal');
    const closeModal = document.getElementById('closeModal');
    const nutritionContent = document.getElementById('nutritionContent');
    
    // Debug nutrition elements
    console.log("Track Nutrition Button found:", !!trackNutritionButton);
    console.log("Nutrition Modal found:", !!nutritionModal);
    console.log("Close Modal Button found:", !!closeModal);

    let currentImage = null;
    let currentRecipeData = null;
    let customPromptHistory = [];
    let selectedGoal = document.getElementById('goal').value;
    let isSelecting = false;
    let startX, startY;
    let overlay, selectionBox;

    // Add event listener for the Track Nutrition button
    trackNutritionButton.addEventListener('click', function() {
        showNutritionSummary();
    });

    // Close modal when clicking the X
    closeModal.addEventListener('click', function() {
        nutritionModal.style.display = 'none';
    });

    // Close modal when clicking outside the content
    window.addEventListener('click', function(event) {
        if (event.target === nutritionModal) {
            nutritionModal.style.display = 'none';
        }
    });

    // Function to show nutrition summary from Telegram bot
    async function showNutritionSummary() {
        nutritionModal.style.display = 'block';
        nutritionContent.innerHTML = '<div class="loading"><div class="spinner"></div><p>Loading nutrition data...</p></div>';
        
        try {
            console.log("Fetching nutrition data from backend...");
            
            // Add a delay to ensure the backend has time to read from the file
            await new Promise(resolve => setTimeout(resolve, 500));
            
            // Try to fetch nutrition summary from the backend
            const response = await fetch('http://localhost:8000/get_nutrition_summary', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json'
                },
                // Add cache-busting parameter to avoid cached responses
                cache: 'no-store'
            });
            
            if (!response.ok) {
                console.error("Server responded with error:", response.status);
                throw new Error(`Server responded with status: ${response.status}`);
            }
            
            const data = await response.json();
            console.log("Received nutrition data:", data);
            
            // Check if there are any foods logged
            if (!data.foods || data.foods.length === 0) {
                nutritionContent.innerHTML = `
                    <div class="result-section">
                        <h3>No Foods Logged Today</h3>
                        <p>You haven't logged any food today using the Telegram bot.</p>
                        <p>To log your nutrition:</p>
                        <ol>
                            <li>Open Telegram and find <strong>@pluggin_food_bot</strong> (Healthy-Food)</li>
                            <li>Tell the bot what you've eaten (e.g., "I had 2 eggs for breakfast")</li>
                            <li>Come back here to see your nutrition summary</li>
                        </ol>
                    </div>
                `;
                return;
            }
            
            // Display the nutrition summary
            let summaryHTML = `
                <div class="result-section">
                    <h3>Foods Logged Today</h3>
                    <ul>
            `;
            
            data.foods.forEach(food => {
                summaryHTML += `<li>${food}</li>`;
            });
            
            summaryHTML += `
                    </ul>
                </div>
                
                <div class="result-section">
                    <h3>Nutrition Summary</h3>
                    <div class="nutrition-grid" style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 15px;">
                        <div><strong>Calories:</strong> ${Math.round(data.nutrition?.calories || 0)} kcal</div>
                        <div><strong>Protein:</strong> ${(data.nutrition?.protein || 0).toFixed(1)}g</div>
                        <div><strong>Carbs:</strong> ${(data.nutrition?.carbs || 0).toFixed(1)}g</div>
                        <div><strong>Fat:</strong> ${(data.nutrition?.fat || 0).toFixed(1)}g</div>
                        <div><strong>Fiber:</strong> ${(data.nutrition?.fiber || 0).toFixed(1)}g</div>
                        <div><strong>Sugar:</strong> ${(data.nutrition?.sugar || 0).toFixed(1)}g</div>
                        <div><strong>Sodium:</strong> ${Math.round(data.nutrition?.sodium || 0)}mg</div>
                    </div>
                </div>
            `;
            
            if (data.recommendations) {
                // Format recommendations to display properly in the extension
                const formattedRecommendations = data.recommendations
                    .replace(/\*\*/g, '') // Remove bold markdown
                    .replace(/\*/g, '')    // Remove italic markdown
                    .replace(/#+\s/g, '')  // Remove heading markdowns
                
                summaryHTML += `
                    <div class="result-section">
                        <h3>Analysis & Recommendations</h3>
                        <div style="white-space: pre-line;">${formattedRecommendations}</div>
                    </div>
                `;
            }
            
            nutritionContent.innerHTML = summaryHTML;
            
        } catch (error) {
            console.error('Error fetching nutrition data:', error);
            
            // Show a helpful error message about server connection
            nutritionContent.innerHTML = `
                <div class="result-section">
                    <h3>Nutrition Tracking with Telegram</h3>
                    <p style="color: #e74c3c; margin-bottom: 15px;">Could not connect to the nutrition server. Make sure your FastAPI server is running.</p>
                    <p>Your nutrition data is tracked through the Telegram bot. To use this feature:</p>
                    <ol>
                        <li>Make sure the FastAPI server is running: <code>python -m uvicorn main:app --reload</code></li>
                        <li>Make sure the Telegram bot is running: <code>python telegram_nutrition_bot.py</code></li>
                        <li>Open Telegram and find <strong>@pluggin_food_bot</strong> (Healthy-Food)</li>
                        <li>Log food by telling the bot what you've eaten (e.g., "I had 2 eggs for breakfast")</li>
                        <li>Use <strong>/summary</strong> to view your nutrition data in Telegram</li>
                    </ol>
                    <p style="margin-top: 20px; text-align: center; font-weight: bold;">Once you've logged food via the Telegram bot, it will appear here!</p>
                </div>
            `;
        }
    }

    // Simple markdown formatter function
    function simpleFormat(text) {
        if (!text) return '';
        
        // First process headings
        text = text
            .replace(/^## (.*?)$/gm, '<h2>$1</h2>')  // Level 2 headings
            .replace(/^### (.*?)$/gm, '<h3>$1</h3>')  // Level 3 headings
            .replace(/^# (.*?)$/gm, '<h1>$1</h1>');  // Level 1 headings
        
        // Then handle lists
        text = text
            .replace(/^\* (.*?)$/gm, '<li>$1</li>')  // List items
            .replace(/<\/li>\s*<li>/g, '</li><li>');  // Fix list spacing
        
        // Finally handle other formatting
        text = text
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')  // Bold
            .replace(/\*(.*?)\*/g, '<em>$1</em>')  // Italic
            .replace(/\n\n/g, '<br><br>')  // Double line breaks
            .replace(/\n/g, '<br>');  // Single line breaks
        
        return text;
    }

    // Handle drag and drop
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.style.borderColor = '#4caf50';
        dropZone.style.backgroundColor = '#f1f8e9';
    });

    dropZone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        dropZone.style.borderColor = '#ccc';
        dropZone.style.backgroundColor = '#f8f9fa';
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.style.borderColor = '#ccc';
        dropZone.style.backgroundColor = '#f8f9fa';
        
        if (e.dataTransfer.files.length > 0) {
            handleFile(e.dataTransfer.files[0]);
        }
    });

    // Handle click upload
    dropZone.addEventListener('click', () => {
        fileInput.click();
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFile(e.target.files[0]);
        }
    });

    // Handle export button
    exportButton.addEventListener('click', () => {
        exportRecipe();
    });
    
    // Handle ask button for custom prompts
    askButton.addEventListener('click', () => {
        sendCustomPrompt();
    });
    
    // Allow pressing Enter in the input field
    customPromptInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            sendCustomPrompt();
        }
    });

    // Add event listeners for new buttons
    downloadButton.addEventListener('click', generatePDF);
    telegramButton.addEventListener('click', sendToTelegram);

    async function handleFile(file) {
        if (!file || !file.type.startsWith('image/')) return;

        // Store current image
        currentImage = file;

        // Get selected goal and log it
        const selectedGoal = document.getElementById('goal').value;
        console.log("Selected dietary goal:", selectedGoal);

        // Show image preview
        const reader = new FileReader();
        reader.onload = function(e) {
            // Create image preview
            imagePreview.innerHTML = '';
            const preview = document.createElement('img');
            preview.src = e.target.result;
            imagePreview.appendChild(preview);
            imagePreview.style.display = 'block';
        }
        reader.readAsDataURL(file);

        loading.style.display = 'block';
        result.innerHTML = '';
        exportButton.style.display = 'none';
        actionButtons.style.display = 'none';
        customPromptSection.style.display = 'none';

        const formData = new FormData();
        formData.append('image', file);
        formData.append('goal', selectedGoal);
        
        try {
            console.log("Fetching from API with FormData...");
            const goalParam = encodeURIComponent(selectedGoal);
            const url = `http://localhost:8000/analyze_recipe?goal=${goalParam}`;
            
            const response = await fetch(url, {
                method: 'POST',
                body: formData
            });
            
            console.log("Response status:", response.status);

            if (!response.ok) {
                throw new Error(`Server error: ${response.status}`);
            }

            const data = await response.json();
            console.log("Response data:", data);
            currentRecipeData = data;
            displayResults(data);
            exportButton.style.display = 'block';
            actionButtons.style.display = 'flex';
            customPromptSection.style.display = 'block';
        } catch (error) {
            console.error('Error:', error);
            result.innerHTML = `
                <div class="result-section">
                    <h3>Error</h3>
                    <p>${error.message}</p>
                </div>
            `;
        } finally {
            loading.style.display = 'none';
        }
    }

    function displayResults(data) {
        result.innerHTML = '';
        
        // Original Analysis
        const originalSection = document.createElement('div');
        originalSection.className = 'result-section';
        originalSection.innerHTML = `
            <h3>${data.section_titles.original}</h3>
            <div class="recipe-content">${data.original_analysis}</div>
        `;
        result.appendChild(originalSection);
        
        // Recipe Analysis with Timeline
        const analysisSection = document.createElement('div');
        analysisSection.className = 'result-section';
        
        // Extract cooking times and create timeline component
        const analysisTimes = extractCookingTimes(data.recipe_analysis);
        const analysisTimeline = createTimelineComponent(analysisTimes);
        
        analysisSection.innerHTML = `
            <h3>${data.section_titles.analysis}</h3>
            <div class="recipe-content">${simpleFormat(data.recipe_analysis)}</div>
            ${analysisTimeline}
        `;
        result.appendChild(analysisSection);
        
        // Modified Recipe with Timeline
        const modifiedSection = document.createElement('div');
        modifiedSection.className = 'result-section';
        
        // Extract modified recipe cooking times and create timeline
        const modifiedTimes = extractCookingTimes(data.modified_recipe);
        const modifiedTimeline = createTimelineComponent(modifiedTimes);
        
        // Get the appropriate dietary badge
        const badgeClass = `${data.dietary_type}-badge`;
        
        modifiedSection.innerHTML = `
            <h3>
                ${data.section_titles.modified}
                <span class="dietary-badge ${badgeClass}">${capitalizeFirst(data.dietary_type)}</span>
            </h3>
            <div class="recipe-content">${simpleFormat(data.modified_recipe)}</div>
            ${modifiedTimeline}
        `;
        result.appendChild(modifiedSection);
        
        // Flavor Enhancement
        const flavorSection = document.createElement('div');
        flavorSection.className = 'result-section';
        flavorSection.innerHTML = `
            <h3>${data.section_titles.flavor}</h3>
            <div class="recipe-content">${simpleFormat(data.flavor_enhancement)}</div>
        `;
        result.appendChild(flavorSection);
        
        // Show the results and hide loading indicator
        loading.style.display = 'none';
        customPromptSection.style.display = 'block';
        customPromptHistory = []; // Reset history for new food
        customResponses.innerHTML = ''; // Clear previous responses
    }

    function capitalizeFirst(str) {
        return str.charAt(0).toUpperCase() + str.slice(1);
    }

    function exportRecipe() {
        if (!currentRecipeData) return;
        
        // Create a printable version
        const printWindow = window.open('', '_blank');
        const dietaryType = currentRecipeData.dietary_type || 'low-carb';
        
        // Get image if available
        let imageHtml = '';
        if (currentRecipeData.image_base64) {
            imageHtml = `<img src="data:image/jpeg;base64,${currentRecipeData.image_base64}" style="max-width: 100%; margin-bottom: 20px; border-radius: 8px;">`;
        }
        
        // Create HTML for custom prompts if any exist
        let customPromptsHtml = '';
        if (customPromptHistory.length > 0) {
            customPromptsHtml = `
                <div class="recipe-section">
                    <h2>Additional Questions</h2>
                    ${customPromptHistory.map(item => `
                        <div style="margin-bottom: 20px;">
                            <h3>Q: ${item.prompt}</h3>
                            <div>${simpleFormat(item.response)}</div>
                        </div>
                    `).join('')}
                </div>
            `;
        }
        
        printWindow.document.write(`
            <!DOCTYPE html>
            <html>
            <head>
                <title>${capitalizeFirst(dietaryType)} Recipe</title>
                <link href="https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700&display=swap" rel="stylesheet">
                <style>
                    body {
                        font-family: 'Nunito', sans-serif;
                        max-width: 800px;
                        margin: 0 auto;
                        padding: 40px;
                        color: #333;
                    }
                    h1, h2, h3 {
                        color: #2c3e50;
                    }
                    .recipe-header {
                        text-align: center;
                        margin-bottom: 30px;
                    }
                    .recipe-section {
                        margin-bottom: 30px;
                    }
                    .dietary-badge {
                        display: inline-block;
                        padding: 5px 10px;
                        color: white;
                        border-radius: 12px;
                        font-size: 14px;
                        font-weight: 600;
                        background-color: #4caf50;
                    }
                    .vegan-badge { background-color: #43a047; }
                    .vegetarian-badge { background-color: #8bc34a; }
                    .low-carb-badge { background-color: #2196f3; }
                    .high-protein-badge { background-color: #ff9800; }
                    ul, ol {
                        padding-left: 25px;
                    }
                    li {
                        margin-bottom: 8px;
                    }
                    @media print {
                        body {
                            padding: 0;
                            font-size: 12pt;
                        }
                    }
                </style>
            </head>
            <body>
                <div class="recipe-header">
                    <h1>${capitalizeFirst(dietaryType)} Version of ${currentRecipeData.original_analysis}</h1>
                    <span class="dietary-badge ${dietaryType}-badge">${capitalizeFirst(dietaryType)}</span>
                </div>
                
                ${imageHtml}
                
                <div class="recipe-section">
                    <h2>Original Food</h2>
                    <p>${currentRecipeData.original_analysis}</p>
                </div>
                
                <div class="recipe-section">
                    <h2>Recipe Analysis</h2>
                    ${simpleFormat(currentRecipeData.recipe_analysis)}
                </div>
                
                <div class="recipe-section">
                    <h2>${capitalizeFirst(dietaryType)} Recipe</h2>
                    ${simpleFormat(currentRecipeData.modified_recipe)}
                </div>
                
                <div class="recipe-section">
                    <h2>Flavor Enhancement</h2>
                    ${simpleFormat(currentRecipeData.flavor_enhancement)}
                </div>
                
                ${customPromptsHtml}
                
                <div class="recipe-footer">
                    <p><em>Created with Recipe Modifier Chrome Extension</em></p>
                </div>
            </body>
            </html>
        `);
        
        printWindow.document.close();
        printWindow.focus();
        
        // Add a short delay before printing
        setTimeout(() => {
            printWindow.print();
        }, 1000);
    }

    // Function to send custom prompt to the server
    async function sendCustomPrompt() {
        const promptText = customPromptInput.value.trim();
        if (!promptText || !currentRecipeData) return;
        
        // Show loading state
        askButton.disabled = true;
        askButton.textContent = 'Loading...';
        
        // Add a temporary placeholder for the loading response
        const tempId = 'temp-response-' + Date.now();
        customResponses.innerHTML = `
            <div id="${tempId}" class="result-section">
                <h3>Q: ${promptText}</h3>
                <div class="recipe-content">
                    <div class="loading">
                        <div class="spinner"></div>
                        <p>Looking up answer...</p>
                    </div>
                </div>
            </div>
        ` + customResponses.innerHTML;
        
        try {
            // Create FormData for the request
            const formData = new FormData();
            formData.append('prompt', promptText);
            formData.append('food_description', currentRecipeData.original_analysis);
            formData.append('dietary_type', currentRecipeData.dietary_type);
            
            // Add the server's response data to provide context
            formData.append('recipe_analysis', currentRecipeData.recipe_analysis);
            formData.append('modified_recipe', currentRecipeData.modified_recipe);
            formData.append('flavor_enhancement', currentRecipeData.flavor_enhancement);
            
            // Send the request to the custom_prompt endpoint
            const response = await fetch('http://localhost:8000/custom_prompt', {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) {
                throw new Error(`Server error: ${response.status}`);
            }
            
            const data = await response.json();
            
            // Add to custom prompt history
            customPromptHistory.push({
                prompt: promptText,
                response: data.response
            });
            
            // Display the updated prompt history
            displayCustomPrompts();
            
            // Clear the input field
            customPromptInput.value = '';
        } catch (error) {
            console.error('Error with custom prompt:', error);
            
            // Remove the temporary loading element
            document.getElementById(tempId)?.remove();
            
            customResponses.innerHTML = `
                <div class="result-section">
                    <h3>Q: ${promptText}</h3>
                    <div class="recipe-content">
                        <p>Error: ${error.message}</p>
                        <p>Please try again later.</p>
                    </div>
                </div>
            ` + customResponses.innerHTML;
        } finally {
            // Reset button state
            askButton.disabled = false;
            askButton.textContent = 'Ask';
        }
    }
    
    // Function to display all custom prompts and responses
    function displayCustomPrompts() {
        // Clear the container
        customResponses.innerHTML = '';
        
        // Add each prompt and response
        customPromptHistory.forEach((item) => {
            const promptDiv = document.createElement('div');
            promptDiv.className = 'result-section';
            promptDiv.innerHTML = `
                <h3>Q: ${item.prompt}</h3>
                <div class="recipe-content">
                    ${simpleFormat(item.response)}
                </div>
            `;
            customResponses.appendChild(promptDiv);
        });
    }

    // Helper function to show toast notification
    function showToast(message, duration = 3000) {
        toast.textContent = message;
        toast.classList.add('show');
        setTimeout(() => {
            toast.classList.remove('show');
        }, duration);
    }

    // Extract cooking time from markdown text
    function extractCookingTimes(markdownText) {
        const timelineSection = markdownText.match(/## Cooking Timeline\s*\n\s*\* Preparation: (\d+) minutes\s*\n\s*\* Cooking: (\d+) minutes\s*\n\s*\* Total: (\d+) minutes/);
        
        if (timelineSection) {
            return {
                prep: parseInt(timelineSection[1]),
                cook: parseInt(timelineSection[2]),
                total: parseInt(timelineSection[3])
            };
        }
        
        // Fallback pattern matching for different formats
        const prepMatch = markdownText.match(/Preparation:?\s*(\d+)\s*minutes/i);
        const cookMatch = markdownText.match(/Cooking:?\s*(\d+)\s*minutes/i);
        const totalMatch = markdownText.match(/Total:?\s*(\d+)\s*minutes/i);
        
        const prep = prepMatch ? parseInt(prepMatch[1]) : 0;
        const cook = cookMatch ? parseInt(cookMatch[1]) : 0;
        const total = totalMatch ? parseInt(totalMatch[1]) : prep + cook;
        
        return { prep, cook, total };
    }

    // Create a visual timeline component
    function createTimelineComponent(times) {
        if (!times || (times.prep === 0 && times.cook === 0)) {
            return ''; // No timeline to show
        }
        
        const prepPercentage = Math.round((times.prep / times.total) * 100);
        const cookPercentage = 100 - prepPercentage;
        
        return `
            <div class="cooking-timeline">
                <h4>Cooking Timeline</h4>
                <div class="timeline-bar">
                    <div class="prep-time" style="width: ${prepPercentage}%">
                        ${prepPercentage > 10 ? `${times.prep}m` : ''}
                    </div>
                    <div class="cook-time" style="width: ${cookPercentage}%">
                        ${cookPercentage > 10 ? `${times.cook}m` : ''}
                    </div>
                </div>
                <div class="timeline-info">
                    <div class="timeline-legend">
                        <div class="legend-item">
                            <div class="legend-color prep-color"></div>
                            <span>Prep: ${times.prep} min</span>
                        </div>
                        <div class="legend-item">
                            <div class="legend-color cook-color"></div>
                            <span>Cook: ${times.cook} min</span>
                        </div>
                    </div>
                    <div class="total-time">Total: ${times.total} minutes</div>
                </div>
            </div>
        `;
    }

    // Fix PDF generation using a direct download approach
    function generatePDF() {
        if (!currentRecipeData) {
            showToast('No recipe data available');
            return;
        }
        
        showToast('Generating PDF...');
        
        try {
            // Create a simple HTML document for the PDF
            let htmlContent = `
            <!DOCTYPE html>
            <html>
            <head>
                <title>${capitalizeFirst(currentRecipeData.dietary_type)} Recipe</title>
                <style>
                    body { font-family: Arial, sans-serif; padding: 20px; }
                    h1, h2 { color: #2c3e50; }
                    .container { max-width: 800px; margin: 0 auto; }
                    .image-container { text-align: center; margin-bottom: 20px; }
                    .image-container img { max-width: 100%; max-height: 300px; border-radius: 8px; }
                    .section { margin-bottom: 20px; }
                    .badge { display: inline-block; padding: 4px 8px; color: white; border-radius: 12px; 
                             font-size: 12px; background-color: #4caf50; margin-left: 10px; }
                    .footer { margin-top: 30px; text-align: center; font-size: 12px; color: #777; }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1 style="text-align: center;">${capitalizeFirst(currentRecipeData.dietary_type)} Recipe</h1>
                    
                    ${currentRecipeData.image_base64 ? 
                        `<div class="image-container">
                            <img src="data:image/jpeg;base64,${currentRecipeData.image_base64}">
                        </div>` : ''}
                    
                    <div class="section">
                        <h2>${currentRecipeData.section_titles.original}</h2>
                        <p>${currentRecipeData.original_analysis}</p>
                    </div>
                    
                    <div class="section">
                        <h2>${currentRecipeData.section_titles.analysis}</h2>
                        <div>${simpleFormat(currentRecipeData.recipe_analysis)}</div>
                    </div>
                    
                    <div class="section">
                        <h2>
                            ${currentRecipeData.section_titles.modified}
                            <span class="badge">${capitalizeFirst(currentRecipeData.dietary_type)}</span>
                        </h2>
                        <div>${simpleFormat(currentRecipeData.modified_recipe)}</div>
                    </div>
                    
                    <div class="section">
                        <h2>${currentRecipeData.section_titles.flavor}</h2>
                        <div>${simpleFormat(currentRecipeData.flavor_enhancement)}</div>
                    </div>
                    
                    <div class="footer">
                        <p>Generated by Recipe Modifier Extension</p>
                        <p>${new Date().toLocaleDateString()}</p>
                    </div>
                </div>
            </body>
            </html>
            `;
            
            // Create a Blob with the HTML content
            const blob = new Blob([htmlContent], { type: 'text/html' });
            const url = URL.createObjectURL(blob);
            
            // Create a download link
            const a = document.createElement('a');
            a.href = url;
            
            // Use a simplified food name (just the main item)
            const foodDescription = currentRecipeData.original_analysis;
            
            // Extract main food item (assume it's typically at the end of the description)
            let mainFood = "food";
            const commonFoods = ["pizza", "burger", "hamburger", "ice cream", "cake", "pasta", "sandwich", "salad", 
                              "taco", "burrito", "sushi", "rice", "steak", "chicken", "fish", "soup"];
            
            // Try to find a common food name in the description
            for (const food of commonFoods) {
                if (foodDescription.toLowerCase().includes(food)) {
                    mainFood = food;
                    break;
                }
            }
            
            // Clean up the food name
            mainFood = mainFood.replace(/\s+/g, "_").toLowerCase();
            
            a.download = `${mainFood}_${currentRecipeData.dietary_type}.html`;
            a.style.display = 'none';
            document.body.appendChild(a);
            
            // Trigger download
            a.click();
            
            // Clean up
            setTimeout(() => {
                URL.revokeObjectURL(url);
                document.body.removeChild(a);
                showToast('Recipe downloaded as HTML');
            }, 100);
            
        } catch (error) {
            console.error('Error generating PDF:', error);
            showToast('Error generating PDF: ' + error.message);
        }
    }

    // Simplify the Telegram function to use text format instead of PDF
    function sendToTelegram() {
        if (!currentRecipeData) {
            showToast('No recipe data available');
            return;
        }
        
        showToast('Sending to Telegram...');
        
        try {
            // Create a simplified text version of the recipe
            const recipeText = `
    *${capitalizeFirst(currentRecipeData.dietary_type)} Recipe*

    *Original Analysis:*
    ${currentRecipeData.original_analysis}

    *Recipe Analysis:*
    ${currentRecipeData.recipe_analysis.replace(/#/g, '')}

    *${capitalizeFirst(currentRecipeData.dietary_type)} Recipe:*
    ${currentRecipeData.modified_recipe.replace(/#/g, '')}

    *Flavor Enhancement:*
    ${currentRecipeData.flavor_enhancement.replace(/#/g, '')}
            `;
            
            // Send the recipe data to the server as text
            fetch('http://localhost:8000/send_to_telegram', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    recipe_data: currentRecipeData,
                    recipe_text: recipeText
                })
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Server error: ' + response.status);
                }
                return response.json();
            })
            .then(data => {
                console.log('Telegram response:', data);
                showToast('Recipe sent to Telegram successfully');
            })
            .catch(error => {
                console.error('Telegram sending error:', error);
                showToast('Error sending to Telegram: ' + error.message);
            });
        } catch (error) {
            console.error('Error preparing Telegram message:', error);
            showToast('Error preparing Telegram message: ' + error.message);
        }
    }

    // Update button icons with proper emoji
    if (downloadButton) {
        downloadButton.textContent = 'Download Entire Recipe';
    }
    
    if (telegramButton) {
        telegramButton.textContent = 'Send Healthier Version';
    }
});
