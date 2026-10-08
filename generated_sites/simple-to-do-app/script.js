const STORAGE_KEY = 'todo_app_tasks';

// FEATURE_001, FEATURE_002: Load data
async function initApp() {
    // Check if key exists; if not, fetch and set.
    if (localStorage.getItem(STORAGE_KEY) === null) {
        try {
            const response = await fetch('./data/data.json');
            const data = await response.json();
            // Ensure the data saved is the tasks array specifically
            // DATA_SPECIFICATION: tasks collection expects list with fields ['id', 'text']
            localStorage.setItem(STORAGE_KEY, JSON.stringify(data.tasks || []));
        } catch (error) {
            console.error('Error loading seed data:', error);
            // Default to empty array if fetch fails
            localStorage.setItem(STORAGE_KEY, JSON.stringify([]));
        }
    }
    renderTasks();
}

// FEATURE_001: Render tasks
function renderTasks() {
    const taskList = document.getElementById('taskList');
    const storedData = localStorage.getItem(STORAGE_KEY);
    const tasks = storedData ? JSON.parse(storedData) : [];
    
    taskList.innerHTML = '';
    tasks.forEach(task => {
        const li = document.createElement('li');
        li.textContent = task.text;
        
        const deleteBtn = document.createElement('button');
        deleteBtn.textContent = 'Delete';
        // FEATURE_002: Delete task
        deleteBtn.onclick = () => deleteTask(task.id);
        
        li.appendChild(deleteBtn);
        taskList.appendChild(li);
    });
}

// FEATURE_001: Add task
function addTask() {
    const input = document.getElementById('taskInput');
    const text = input.value.trim();
    
    if (!text) {
        alert('Input cannot be empty.');
        return;
    }
    
    const tasks = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
    const newTask = {
        id: Date.now(),
        text: text
    };
    
    tasks.push(newTask);
    // Explicitly write back to localStorage using the correct key
    localStorage.setItem(STORAGE_KEY, JSON.stringify(tasks));
    input.value = '';
    renderTasks();
}

// FEATURE_002: Delete task
function deleteTask(id) {
    let tasks = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
    tasks = tasks.filter(task => task.id !== id);
    // Explicitly write back to localStorage using the correct key
    localStorage.setItem(STORAGE_KEY, JSON.stringify(tasks));
    renderTasks();
}

document.getElementById('addBtn').addEventListener('click', addTask);
window.onload = initApp;
