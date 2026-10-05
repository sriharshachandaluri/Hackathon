document.addEventListener('DOMContentLoaded', () => {
    const taskForm = document.getElementById('add-task-form');
    const taskTitleInput = document.getElementById('task-title');
    const taskList = document.getElementById('task-list');

    // FEATURE_002: Fetch tasks from GET /tasks
    const fetchTasks = async () => {
        try {
            const response = await fetch('/tasks');
            if (!response.ok) throw new Error('Failed to fetch tasks');
            const tasks = await response.json();
            renderTasks(tasks);
        } catch (error) {
            console.error(error);
            alert('Error fetching tasks');
        }
    };

    const renderTasks = (tasks) => {
        taskList.innerHTML = '';
        tasks.forEach(task => {
            const li = document.createElement('li');
            li.textContent = task.title;
            taskList.appendChild(li);
        });
    };

    // FEATURE_001: Save task via POST /tasks
    taskForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const title = taskTitleInput.value.trim();
        if (!title) {
            alert('Title must not be empty');
            return;
        }

        try {
            const response = await fetch('/tasks', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title })
            });
            if (!response.ok) throw new Error('Failed to save task');
            
            taskTitleInput.value = '';
            fetchTasks();
        } catch (error) {
            console.error(error);
            alert('Error saving task');
        }
    });

    fetchTasks();
});