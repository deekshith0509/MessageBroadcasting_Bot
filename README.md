# Advanced and Secured Message Broadcasting Bot


" Advanced and Secured Message Broadcasting Bot " is a Telegram bot that allows users to anonymously submit secrets, like and comment on them, and manages subscriptions and broadcasts. It uses SQLite for storing data and the `cryptography` library for encrypting secrets.

## Features

- **Anonymous Secret Submission**: Users can submit secrets anonymously.
- **Likes and Comments**: Users can like and comment on secrets.
- **Subscription Management**: Users are automatically subscribed to receive broadcasted secrets.
- **Encryption**: Secrets are encrypted to ensure privacy and security.
- **Asynchronous Operations**: The bot handles commands and interactions asynchronously.
- **Broadcasting**: Secrets are broadcasted to all subscribed users.
- **Secret Deletion**: Users can delete their secrets.

## Technologies Used

- Python
- Telegram Bot API
- SQLite
- cryptography (Fernet)
- asyncio

## Setup Instructions

### Prerequisites

- Python 3.7+
- A Telegram account and a bot token from BotFather

### Installation

1. **Clone the repository:**
    ```sh
    git clone https://github.com/yourusername/secret-bot.git
    cd secret-bot
    ```

2. **Create a virtual environment and activate it:**
    ```sh
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3. **Install the required packages:**
    ```sh
    pip install -r requirements.txt
    ```

4. **Set up the database:**
    ```sh
    python -c "from your_script import setup_database; setup_database()"
    ```

5. **Configure the bot token:**
    - Create a file named `.env` in the project root directory.
    - Add the following line to the `.env` file:
      ```env
      BOT_TOKEN=your-telegram-bot-token
      ```

6. **Run the bot:**
    ```sh
    python your_script.py
    ```

## Usage

### Bot Commands

- **/start**: Show the welcome message and available commands.
- **/view**: View your submitted secrets and their status.
- **/status**: View the status of your submitted secrets, including likes and comments.
- **/delete <secret_id>**: Delete your submitted secret by providing its ID.
- **/deleteimp**: Delete the most recent secret from all devices.

### Submitting Secrets

- Send a message to the bot to submit an anonymous secret.

### Liking and Commenting

- Use the buttons below the secrets to like or comment on them.

## Code Overview

### Database Setup

The `setup_database` function initializes the SQLite database and creates the required tables.

### Encryption

The `get_cipher_suite` and `get_user_key` functions handle the encryption and decryption of secrets using Fernet from the `cryptography` library.

### Bot Command Handlers

- **start**: Handles the `/start` command.
- **view**: Handles the `/view` command.
- **status**: Handles the `/status` command.
- **delete**: Handles the `/delete` command.
- **deleteimp**: Handles the `/deleteimp` command.
- **secret**: Handles the submission of secrets.
- **like**: Handles the liking of secrets.
- **comment**: Handles the commenting on secrets.
- **process_comment**: Processes comments on secrets.

### Broadcasting and Deletion

- **broadcast**: Broadcasts a new secret to all subscribed users.
- **delete_broadcasted_messages**: Deletes broadcasted messages from all devices.
- **schedule_deletion**: Schedules deletion of messages.



