// Sample matches data - you can update this with real tournament data
const matches = [
    {
        id: 1,
        team1: "Brazil",
        team2: "Italy",
        date: "2024-09-15",
        time: "14:00",
        round: "Quarter Final 1"
    },
    {
        id: 2,
        team1: "USA",
        team2: "Poland",
        date: "2024-09-15",
        time: "17:00",
        round: "Quarter Final 2"
    },
    {
        id: 3,
        team1: "Serbia",
        team2: "Turkey",
        date: "2024-09-16",
        time: "14:00",
        round: "Quarter Final 3"
    },
    {
        id: 4,
        team1: "Japan",
        team2: "China",
        date: "2024-09-16",
        time: "17:00",
        round: "Quarter Final 4"
    },
    {
        id: 5,
        team1: "TBD",
        team2: "TBD",
        date: "2024-09-18",
        time: "15:00",
        round: "Semi Final 1"
    },
    {
        id: 6,
        team1: "TBD",
        team2: "TBD",
        date: "2024-09-18",
        time: "18:00",
        round: "Semi Final 2"
    },
    {
        id: 7,
        team1: "TBD",
        team2: "TBD",
        date: "2024-09-20",
        time: "16:00",
        round: "Final"
    }
];

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
    loadMatches();
    loadLeaderboard();
    setupNavigation();
});

function initializeApp() {
    // Initialize local storage if it doesn't exist
    if (!localStorage.getItem('predictions')) {
        localStorage.setItem('predictions', JSON.stringify({}));
    }
    if (!localStorage.getItem('players')) {
        localStorage.setItem('players', JSON.stringify([]));
    }
}

function setupNavigation() {
    const navLinks = document.querySelectorAll('.nav-links a');
    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const targetId = this.getAttribute('href').substring(1);
            showSection(targetId);
        });
    });
}

function showSection(sectionId) {
    // Hide all sections
    const sections = document.querySelectorAll('.section');
    sections.forEach(section => {
        section.classList.remove('active');
    });
    
    // Show target section
    const targetSection = document.getElementById(sectionId);
    if (targetSection) {
        targetSection.classList.add('active');
    }
    
    // Reload content based on section
    if (sectionId === 'predictions') {
        loadMatches();
    } else if (sectionId === 'leaderboard') {
        loadLeaderboard();
    }
}

function loadMatches() {
    const container = document.getElementById('matches-container');
    const predictions = JSON.parse(localStorage.getItem('predictions') || '{}');
    
    container.innerHTML = matches.map(match => `
        <div class="match-card">
            <div class="match-header">
                ${match.round} - ${match.date} at ${match.time}
            </div>
            <div class="match-teams">
                <div class="team">
                    <div class="team-name">${match.team1}</div>
                </div>
                <div class="vs">VS</div>
                <div class="team">
                    <div class="team-name">${match.team2}</div>
                </div>
            </div>
            <div class="prediction-buttons">
                <button class="team-btn ${predictions[match.id] === match.team1 ? 'selected' : ''}" 
                        onclick="makePrediction(${match.id}, '${match.team1}')"
                        ${match.team1 === 'TBD' ? 'disabled' : ''}>
                    ${match.team1}
                </button>
                <button class="team-btn ${predictions[match.id] === match.team2 ? 'selected' : ''}" 
                        onclick="makePrediction(${match.id}, '${match.team2}')"
                        ${match.team2 === 'TBD' ? 'disabled' : ''}>
                    ${match.team2}
                </button>
            </div>
        </div>
    `).join('');
}

function makePrediction(matchId, team) {
    const predictions = JSON.parse(localStorage.getItem('predictions') || '{}');
    predictions[matchId] = team;
    localStorage.setItem('predictions', JSON.stringify(predictions));
    
    // Update the UI
    loadMatches();
    
    // Show feedback
    showNotification(`Prediction saved: ${team} to win!`);
}

function addPlayer() {
    const nameInput = document.getElementById('player-name');
    const playerName = nameInput.value.trim();
    
    if (!playerName) {
        showNotification('Please enter your name!', 'error');
        return;
    }
    
    const players = JSON.parse(localStorage.getItem('players') || '[]');
    
    // Check if player already exists
    if (players.find(p => p.name === playerName)) {
        showNotification('Player name already exists!', 'error');
        return;
    }
    
    // Add new player
    players.push({
        name: playerName,
        score: 0,
        predictions: 0,
        correct: 0
    });
    
    localStorage.setItem('players', JSON.stringify(players));
    nameInput.value = '';
    
    loadLeaderboard();
    showNotification(`Welcome ${playerName}!`);
}

function loadLeaderboard() {
    const container = document.getElementById('leaderboard-table');
    const players = JSON.parse(localStorage.getItem('players') || '[]');
    
    // Sort players by score
    players.sort((a, b) => b.score - a.score);
    
    if (players.length === 0) {
        container.innerHTML = '<p style="text-align: center; color: white; margin-top: 2rem;">No players yet. Join the game to get started!</p>';
        return;
    }
    
    container.innerHTML = `
        <div class="leaderboard-table">
            <table>
                <thead>
                    <tr>
                        <th>Rank</th>
                        <th>Player</th>
                        <th>Score</th>
                        <th>Predictions</th>
                        <th>Correct</th>
                        <th>Accuracy</th>
                    </tr>
                </thead>
                <tbody>
                    ${players.map((player, index) => `
                        <tr>
                            <td>${index + 1}</td>
                            <td>${player.name}</td>
                            <td>${player.score}</td>
                            <td>${player.predictions}</td>
                            <td>${player.correct}</td>
                            <td>${player.predictions > 0 ? Math.round((player.correct / player.predictions) * 100) : 0}%</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
    `;
}

function showNotification(message, type = 'success') {
    // Remove existing notification
    const existing = document.querySelector('.notification');
    if (existing) {
        existing.remove();
    }
    
    // Create notification
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 100px;
        right: 20px;
        background: ${type === 'error' ? '#e74c3c' : '#27ae60'};
        color: white;
        padding: 1rem 2rem;
        border-radius: 5px;
        box-shadow: 0 5px 15px rgba(0,0,0,0.2);
        z-index: 1001;
        animation: slideIn 0.3s ease;
    `;
    
    document.body.appendChild(notification);
    
    // Remove after 3 seconds
    setTimeout(() => {
        notification.remove();
    }, 3000);
}

// Add CSS animation for notifications
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
`;
document.head.appendChild(style);

// Admin functions for updating results (you can call these from browser console)
function updateMatchResult(matchId, winner) {
    const predictions = JSON.parse(localStorage.getItem('predictions') || '{}');
    const players = JSON.parse(localStorage.getItem('players') || '[]');
    
    // Update player scores based on correct predictions
    players.forEach(player => {
        if (predictions[matchId] === winner) {
            player.score += 3;
            player.correct += 1;
        }
        player.predictions += 1;
    });
    
    localStorage.setItem('players', JSON.stringify(players));
    loadLeaderboard();
    
    console.log(`Match ${matchId} result updated. Winner: ${winner}`);
}

// Example: updateMatchResult(1, "Brazil") - call this in console to update results