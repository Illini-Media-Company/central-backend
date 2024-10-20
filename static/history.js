// main.js - Handles history for both request path and request body

document.addEventListener('DOMContentLoaded', function () {
    const requestPathInput = document.getElementById('request-path');
    const requestBodyInput = document.getElementById('request-body');
    const requestPathHistoryList = document.getElementById('request-path-history');
    const requestBodyHistoryList = document.getElementById('request-body-history');

    const pathHistoryKey = 'requestPathHistory';   // Key for request path history in localStorage
    const bodyHistoryKey = 'requestBodyHistory';   // Key for request body history in localStorage

    // Load previous request path history from localStorage
    function loadRequestPathHistory() {
        const history = JSON.parse(localStorage.getItem(pathHistoryKey)) || [];
        return history;
    }

    // Load previous request body history from localStorage
    function loadRequestBodyHistory() {
        const history = JSON.parse(localStorage.getItem(bodyHistoryKey)) || [];
        return history;
    }

    // Save new input to localStorage for request path
    function saveRequestPathHistory(input) {
        const history = loadRequestPathHistory();
        if (!history.includes(input)) {
            history.push(input);
            localStorage.setItem(pathHistoryKey, JSON.stringify(history));
        }
    }

    // Save new input to localStorage for request body
    function saveRequestBodyHistory(input) {
        const history = loadRequestBodyHistory();
        if (!history.includes(input)) {
            history.push(input);
            localStorage.setItem(bodyHistoryKey, JSON.stringify(history));
        }
    }

    // Show history list as dropdown for request path
    function showRequestPathHistory() {
        const history = loadRequestPathHistory();
        requestPathHistoryList.innerHTML = ''; // Clear current dropdown

        history.forEach(function (item) {
            const listItem = document.createElement('li');
            listItem.textContent = item;
            listItem.classList.add('dropdown-item');
            listItem.addEventListener('click', function () {
                requestPathInput.value = item;  // Set input value to selected history item
                requestPathHistoryList.style.display = 'none';
            });
            requestPathHistoryList.appendChild(listItem);
        });

        if (history.length > 0) {
            requestPathHistoryList.style.display = 'block';
        } else {
            requestPathHistoryList.style.display = 'none';
        }
    }

    // Show history list as dropdown for request body
    function showRequestBodyHistory() {
        const history = loadRequestBodyHistory();
        requestBodyHistoryList.innerHTML = ''; // Clear current dropdown

        history.forEach(function (item) {
            const listItem = document.createElement('li');
            listItem.textContent = item;
            listItem.classList.add('dropdown-item');
            listItem.addEventListener('click', function () {
                requestBodyInput.value = item;  // Set input value to selected history item
                requestBodyHistoryList.style.display = 'none';
            });
            requestBodyHistoryList.appendChild(listItem);
        });

        if (history.length > 0) {
            requestBodyHistoryList.style.display = 'block';
        } else {
            requestBodyHistoryList.style.display = 'none';
        }
    }

    // Listen for input event in the request path field to show history
    requestPathInput.addEventListener('input', function () {
        const currentValue = requestPathInput.value;
        if (currentValue === '') {
            requestPathHistoryList.style.display = 'none';
        } else {
            showRequestPathHistory();
        }
    });

    // Listen for input event in the request body field to show history
    requestBodyInput.addEventListener('input', function () {
        const currentValue = requestBodyInput.value;
        if (currentValue === '') {
            requestBodyHistoryList.style.display = 'none';
        } else {
            showRequestBodyHistory();
        }
    });

    // Save request path when the form is submitted
    document.querySelector('form').addEventListener('submit', function () {
        const requestPath = requestPathInput.value.trim();
        const requestBody = requestBodyInput.value.trim();

        if (requestPath !== '') {
            saveRequestPathHistory(requestPath);  // Save path to history if not empty
        }

        if (requestBody !== '') {
            saveRequestBodyHistory(requestBody);  // Save body to history if not empty
        }
    });

    // Hide the history dropdown if clicking outside for both request path and body
    document.addEventListener('click', function (e) {
        if (!requestPathHistoryList.contains(e.target) && e.target !== requestPathInput) {
            requestPathHistoryList.style.display = 'none';
        }
        if (!requestBodyHistoryList.contains(e.target) && e.target !== requestBodyInput) {
            requestBodyHistoryList.style.display = 'none';
        }
    });
});
