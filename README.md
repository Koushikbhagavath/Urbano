# Urbano - Smart City Complaint Management

## Overview
Urbano is a comprehensive platform for citizens to lodge civic complaints and for municipal departments to manage and resolve them efficiently.

## Components
1. **Urbano Mobile App (urbano_mobile/)**: Flutter-based mobile application used by citizens to register, submit complaints with media, and track status.
2. **Web Portal**: HTML/JS dashboard for Managers, Departments, and Admins to view complaints, assign tasks, and monitor system statistics.
3. **Backend Server (pp.py)**: Python Flask REST API handling authentication, database interactions, and real-time updates via Server-Sent Events (SSE).
4. **Database**: MySQL relational database holding structured records of users, complaints, and organizational roles.

## How to Run Locally
1. Import the SQL database schema into your local MySQL server.
2. Set up a Python virtual environment: python -m venv venv and install dependencies from pp.py.
3. Run the Flask server: python app.py (Default port: 8080).
4. For the mobile app, navigate to urbano_mobile/, run lutter pub get, and deploy to a device or emulator.
