// server.js - Simple Signaling Server for Chattelo
const express = require('express');
const http = require('http');
const socketIo = require('socket.io');
const cors = require('cors');

const app = express();
const server = http.createServer(app);
const io = socketIo(server, {
  cors: {
    origin: "*",
    methods: ["GET", "POST"]
  }
});

app.use(cors());
app.use(express.json());

// Store waiting users and active connections
let waitingUsers = new Set();
let activeConnections = new Map();

io.on('connection', (socket) => {
  console.log('🔗 User connected:', socket.id);

  socket.on('join-chat', (userData) => {
    console.log('👤 User wants to chat:', socket.id, userData);
    
    // Add user to waiting list
    waitingUsers.add(socket.id);
    
    // Try to match with someone
    tryToMatchUsers(socket);
    
    // Update all clients about online users
    updateOnlineCount();
  });

  socket.on('send-message', (data) => {
    // Forward message to the partner
    if (activeConnections.has(socket.id)) {
      const partnerId = activeConnections.get(socket.id);
      io.to(partnerId).emit('receive-message', {
        text: data.text,
        sender: 'partner',
        timestamp: new Date()
      });
    }
  });

  socket.on('typing', (isTyping) => {
    // Forward typing indicator
    if (activeConnections.has(socket.id)) {
      const partnerId = activeConnections.get(socket.id);
      io.to(partnerId).emit('partner-typing', isTyping);
    }
  });

  socket.on('skip-partner', () => {
    disconnectUser(socket.id);
    // Re-add to waiting list
    waitingUsers.add(socket.id);
    tryToMatchUsers(socket);
  });

  socket.on('disconnect', () => {
    console.log('❌ User disconnected:', socket.id);
    disconnectUser(socket.id);
    updateOnlineCount();
  });

  function disconnectUser(userId) {
    // Remove from waiting
    waitingUsers.delete(userId);
    
    // Disconnect from partner
    if (activeConnections.has(userId)) {
      const partnerId = activeConnections.get(userId);
      io.to(partnerId).emit('partner-disconnected');
      activeConnections.delete(partnerId);
      activeConnections.delete(userId);
    }
  }

  function tryToMatchUsers(newUserSocket) {
    if (waitingUsers.size >= 2) {
      // Get two users from waiting list
      const users = Array.from(waitingUsers);
      const user1 = users[0];
      const user2 = users[1];
      
      if (user1 && user2 && user1 !== user2) {
        // Remove them from waiting list
        waitingUsers.delete(user1);
        waitingUsers.delete(user2);
        
        // Create connection between them
        activeConnections.set(user1, user2);
        activeConnections.set(user2, user1);
        
        // Notify both users
        io.to(user1).emit('matched', { partnerId: user2 });
        io.to(user2).emit('matched', { partnerId: user1 });
        
        console.log('🤝 Matched users:', user1, user2);
      }
    }
  }

  function updateOnlineCount() {
    const onlineCount = io.engine.clientsCount;
    io.emit('online-count', { 
      online: onlineCount,
      waiting: waitingUsers.size,
      active: activeConnections.size / 2
    });
  }
});

// Start server
const PORT = process.env.PORT || 3000;
server.listen(PORT, () => {
  console.log(`🚀 Chattelo Signaling Server running on port ${PORT}`);
  console.log(`🌍 Connect via: http://localhost:${PORT}`);
});
