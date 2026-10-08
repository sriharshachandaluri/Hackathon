// FEATURE_001: Arithmetic Operations Logic

let currentInput = '';

function updateDisplay(value) {
    // FEATURE_001: updateDisplay
    const display = document.getElementById('display');
    display.textContent = value;
}

function handleButtonClick(value) {
    // FEATURE_001: handleButtonClick
    if (value === 'C') {
        currentInput = '';
        updateDisplay('0');
        return;
    }
    
    currentInput += value;
    updateDisplay(currentInput);
}

function calculateResult() {
    // FEATURE_001: calculateResult
    try {
        // Basic safety check for division by zero
        if (currentInput.includes('/0')) {
            updateDisplay('Error');
            currentInput = '';
            return;
        }

        // Eval is used for simplicity in standard calculator logic per requirements
        const result = eval(currentInput);
        
        if (result === undefined || isNaN(result) || !isFinite(result)) {
            throw new Error();
        }

        currentInput = result.toString();
        updateDisplay(currentInput);
    } catch (e) {
        updateDisplay('Error');
        currentInput = '';
    }
}
