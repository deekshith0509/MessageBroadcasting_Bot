import os
import sqlite3
from cryptography.fernet import Fernet
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, CallbackContext

# Initialize database
def setup_database():
    conn = sqlite3.connect('secrets.db', check_same_thread=False)
    c = conn.cursor()

    # Create tables if they don't exist
    c.execute('''CREATE TABLE IF NOT EXISTS Secrets
                 (id INTEGER PRIMARY KEY, user_id INTEGER, content BLOB, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, comments_count INTEGER DEFAULT 0, likes_count INTEGER DEFAULT 0)''')

    c.execute('''CREATE TABLE IF NOT EXISTS Comments
                 (id INTEGER PRIMARY KEY, secret_id INTEGER, user_id INTEGER, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')

    c.execute('''CREATE TABLE IF NOT EXISTS Likes
                 (secret_id INTEGER, user_id INTEGER, PRIMARY KEY (secret_id, user_id))''')

    c.execute('''CREATE TABLE IF NOT EXISTS SubscribedUsers
                 (user_id INTEGER PRIMARY KEY)''')

    c.execute('''CREATE TABLE IF NOT EXISTS Keys
                 (user_id INTEGER PRIMARY KEY, key BLOB)''')

    # Table to track broadcasted messages and their IDs
    c.execute('''CREATE TABLE IF NOT EXISTS BroadcastedMessages
                 (secret_id INTEGER, user_id INTEGER, message_id INTEGER, PRIMARY KEY (secret_id, user_id))''')

    conn.commit()
    conn.close()



setup_database()

def get_db_connection():
    conn = sqlite3.connect('secrets.db', check_same_thread=False)
    return conn

def get_cipher_suite(user_id):
    key = get_user_key(user_id)
    return Fernet(key)

def get_user_key(user_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT key FROM Keys WHERE user_id = ?", (user_id,))
    result = c.fetchone()

    if result:
        key = result[0]
    else:
        key = Fernet.generate_key()
        c.execute("INSERT INTO Keys (user_id, key) VALUES (?, ?)", (user_id, key))
        conn.commit()

    conn.close()
    return key

async def start(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    add_user_subscription(user_id)
    commands_info = (
        "Welcome to the Secret Bot! Here are the commands you can use:\n\n"
        "/start - Show the welcome message and available commands.\n"
        "/view - View your submitted secrets and their status.\n"
        "/status - View the status of your submitted secrets, including likes and comments.\n"
        "/delete <secret_id> - Delete your submitted secret by providing its ID.\n"
        "/deleteimp - Delete the most recent secret from all devices.\n"
        "\nSubmit your anonymous secret by sending a message. You can also like or comment on secrets submitted by others.\n\n"
        "Use the buttons below the secrets to like or comment on them. Note: Avoid sharing personal information."
    )
    await update.message.reply_text(commands_info)


async def broadcast(secret_id: int, bot):
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Fetch the encrypted content and sender_id for the secret
        c.execute("SELECT content, user_id FROM Secrets WHERE id = ?", (secret_id,))
        secret = c.fetchone()
        
        if secret:
            encrypted_content, sender_id = secret
            cipher_suite = get_cipher_suite(sender_id)  # Get the cipher suite for the sender
            content = cipher_suite.decrypt(encrypted_content).decode('utf-8')  # Decrypt and decode content
            
            # Retrieve all subscribed users
            c.execute("SELECT user_id FROM SubscribedUsers")
            subscribed_users = c.fetchall()
            
            if not subscribed_users:
                print("No subscribed users to broadcast to.")
                return
            
            for user_id_tuple in subscribed_users:
                user_id = user_id_tuple[0]
                
                try:
                    # Send the decrypted content to the user with dynamic inline buttons
                    message = await bot.send_message(
                        user_id,
                        f"New Secret Broadcasted:\n{content}",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("Like", callback_data=f'like_{secret_id}'),
                             InlineKeyboardButton("Comment", callback_data=f'comment_{secret_id}')]
                        ])
                    )

                    # Optionally, store the message ID for future reference
                    c.execute("INSERT INTO BroadcastedMessages (secret_id, user_id, message_id) VALUES (?, ?, ?)",
                              (secret_id, user_id, message.message_id))
                    conn.commit()

                except Exception as e:
                    print(f"Error sending secret to user {user_id}: {e}")
                    # Notify user of an issue
                    await bot.send_message(user_id, "An error occurred while processing the secret. Please try again later.")
        
        conn.close()
    except Exception as e:
        print(f"Error broadcasting secret: {e}")


async def delete_broadcasted_messages(secret_id: int, bot):
    try:
        conn = get_db_connection()
        c = conn.cursor()

        # Fetch all message IDs for the given secret
        c.execute("SELECT user_id, message_id FROM BroadcastedMessages WHERE secret_id = ?", (secret_id,))
        messages = c.fetchall()

        for user_id, message_id in messages:
            try:
                # Delete the message from the user's chat
                await bot.delete_message(chat_id=user_id, message_id=message_id)
            except Exception as e:
                print(f"Error deleting message {message_id} for user {user_id}: {e}")

        # Clean up the BroadcastedMessages table
        c.execute("DELETE FROM BroadcastedMessages WHERE secret_id = ?", (secret_id,))
        conn.commit()
        conn.close()

    except Exception as e:
        print(f"Error deleting broadcasted messages: {e}")


# Define the schedule_deletion function if needed
async def schedule_deletion(message_id, chat_id, bot):
    # Wait for 3 days (in seconds)
    await asyncio.sleep(3 * 24 * 60 * 60)  # 3 days in seconds
    try:
        await bot.delete_message(chat_id, message_id)
    except Exception as e:
        print(f"Error deleting message {message_id}: {e}")


async def secret(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    cipher_suite = get_cipher_suite(user_id)

    if context.user_data.get('in_comment_mode'):
        # If in comment mode, process as a comment
        await process_comment(update, context)
        return

    secret_text = update.message.text
    encrypted_secret = cipher_suite.encrypt(secret_text.encode('utf-8'))

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO Secrets (user_id, content) VALUES (?, ?)", (user_id, encrypted_secret))
    secret_id = c.lastrowid
    conn.commit()
    conn.close()

    await update.message.reply_text("Your secret has been submitted anonymously!")

    # Notify all subscribed users
    await broadcast(secret_id, context.bot)  # Pass context.bot to broadcast

    # Notify the original sender that the secret was broadcasted
    await update.message.reply_text(f"Your secret #{secret_id} has been broadcasted to all users.")



async def like(update: Update, context: CallbackContext):
    try:
        query = update.callback_query
        user_id = query.from_user.id
        secret_id = int(query.data.split('_')[1])

        conn = get_db_connection()
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO Likes (secret_id, user_id) VALUES (?, ?)", (secret_id, user_id))
        c.execute("UPDATE Secrets SET likes_count = likes_count + 1 WHERE id = ?", (secret_id,))
        conn.commit()
        conn.close()

        await query.answer("You liked this secret!")
        await query.edit_message_text(text=f"You liked Secret #{secret_id}")
    except Exception as e:
        print(f"Error liking secret: {e}")
        await query.answer("An error occurred. Please try again later.")

async def comment(update: Update, context: CallbackContext):
    try:
        query = update.callback_query
        secret_id = int(query.data.split('_')[1])

        # Set the secret ID to user data for processing comment
        context.user_data['in_comment_mode'] = secret_id
        await query.message.reply_text("Please enter your comment:")

        await query.answer("You can now send your comment.")
    except Exception as e:
        print(f"Error preparing comment: {e}")
        await query.answer("An error occurred. Please try again later.")

import uuid

def generate_unique_id():
    return str(uuid.uuid4())


async def process_comment(update: Update, context: CallbackContext):
    try:
        if 'in_comment_mode' in context.user_data:
            secret_id = context.user_data.pop('in_comment_mode')
            comment_text = update.message.text

            conn = get_db_connection()
            c = conn.cursor()
            # Insert comment without encryption and without user ID
            c.execute("INSERT INTO Comments (secret_id, content) VALUES (?, ?)", (secret_id, comment_text))
            c.execute("UPDATE Secrets SET comments_count = comments_count + 1 WHERE id = ?", (secret_id,))
            conn.commit()
            conn.close()

            await update.message.reply_text("Your comment has been added anonymously!")

            # Notify about the comment on the original secret
            await update.message.reply_text(f"Comment added to Secret #{secret_id}:\n[Redacted]")

        else:
            # If not in comment mode, treat it as a secret message
            await secret(update, context)
    except Exception as e:
        print(f"Error submitting comment: {e}")
        await update.message.reply_text("An error occurred while submitting your comment. Please try again later.")



async def view(update: Update, context: CallbackContext):
    try:
        user_id = update.message.from_user.id
        conn = get_db_connection()
        c = conn.cursor()

        # Fetch user secrets
        c.execute("SELECT id, content, comments_count, likes_count FROM Secrets WHERE user_id = ? ORDER BY timestamp DESC", (user_id,))
        secrets = c.fetchall()

        if secrets:
            for secret in secrets:
                secret_id, encrypted_content, comments_count, likes_count = secret
                cipher_suite = get_cipher_suite(user_id)
                try:
                    content = cipher_suite.decrypt(encrypted_content).decode('utf-8')
                except Exception as e:
                    content = f"[Decryption Error: {str(e)}]"

                # Fetch comments for the secret
                c.execute("SELECT content, timestamp FROM Comments WHERE secret_id = ?", (secret_id,))
                comments = c.fetchall()

                comments_text = "\n".join([
                    f"Comment {i+1}: {comment[0]} (Posted on: {comment[1]})"
                    for i, comment in enumerate(comments)
                ])

                if not comments_text:
                    comments_text = "No comments."

                await update.message.reply_text(
                    f"Secret #{secret_id}:\n{content}\nComments ({comments_count}):\n{comments_text}\nLikes: {likes_count}",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("Like", callback_data=f'like_{secret_id}'),
                         InlineKeyboardButton("Comment", callback_data=f'comment_{secret_id}')]
                    ])
                )
        else:
            await update.message.reply_text("No secrets found.")
        
        conn.close()
    except sqlite3.Error as e:
        await update.message.reply_text(f"Database error while retrieving your secrets: {str(e)}")
        print(f"Database error: {str(e)}")
    except Exception as e:
        await update.message.reply_text(f"An error occurred while retrieving your secrets: {str(e)}")
        print(f"Error viewing secrets: {str(e)}")




async def status(update: Update, context: CallbackContext):
    try:
        user_id = update.message.from_user.id
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT id, content, comments_count, likes_count FROM Secrets WHERE user_id = ? ORDER BY timestamp DESC", (user_id,))
        secrets = c.fetchall()

        if secrets:
            for secret in secrets:
                secret_id, encrypted_content, comments_count, likes_count = secret
                cipher_suite = get_cipher_suite(user_id)
                try:
                    content = cipher_suite.decrypt(encrypted_content).decode('utf-8')
                except Exception as e:
                    content = "[Decryption Error]"

                await update.message.reply_text(
                    f"Secret #{secret_id}:\nContent: {content}\nComments Count: {comments_count}\nLikes Count: {likes_count}"
                )
        else:
            await update.message.reply_text("No secrets found.")
    except Exception as e:
        print(f"Error showing status: {e}")
        await update.message.reply_text("An error occurred while retrieving the status of your secrets. Please try again later.")


# Assuming you have a way to track devices or sessions
async def notify_all_devices(secret_id, bot):
    try:
        # Fetch all devices or users that received the secret
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT user_id FROM SubscribedUsers")
        users = c.fetchall()
        conn.close()

        for user_id_tuple in users:
            user_id = user_id_tuple[0]
            try:
                # Notify each user to delete the secret
                await bot.send_message(user_id, f"Secret #{secret_id} has been deleted from all devices.")
                # Optionally, you can implement more specific deletion commands
                # to remove the secret from their device's local storage.
            except Exception as e:
                print(f"Error notifying user {user_id}: {e}")
    except Exception as e:
        print(f"Error notifying devices about secret {secret_id}: {e}")


async def deleteimp(update: Update, context: CallbackContext):
    try:
        user_id = update.message.from_user.id

        conn = get_db_connection()
        c = conn.cursor()

        # Find the most recent secret for the user
        c.execute("SELECT id FROM Secrets WHERE user_id = ? ORDER BY timestamp DESC LIMIT 1", (user_id,))
        result = c.fetchone()

        if result:
            secret_id = result[0]

            # Delete the secret and associated comments and likes
            c.execute("DELETE FROM Secrets WHERE id = ?", (secret_id,))
            c.execute("DELETE FROM Comments WHERE secret_id = ?", (secret_id,))
            c.execute("DELETE FROM Likes WHERE secret_id = ?", (secret_id,))
            conn.commit()

            # Delete broadcasted messages from all devices
            await delete_broadcasted_messages(secret_id, context.bot)

            await update.message.reply_text(f"The most recent secret #{secret_id} has been deleted from all devices.")

        else:
            await update.message.reply_text("No secrets found for you.")

        conn.close()
    except Exception as e:
        print(f"Error deleting the most recent secret: {e}")
        await update.message.reply_text("An error occurred while deleting the most recent secret. Please try again later.")


def add_user_subscription(user_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO SubscribedUsers (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

def get_subscribed_users():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT user_id FROM SubscribedUsers")
    users = [row[0] for row in c.fetchall()]
    conn.close()
    return users

async def delete_secret(update: Update, context: CallbackContext):
    try:
        if context.args:
            secret_id = int(context.args[0])
            user_id = update.message.from_user.id

            conn = get_db_connection()
            c = conn.cursor()

            # Check if the secret belongs to the user
            c.execute("SELECT user_id FROM Secrets WHERE id = ?", (secret_id,))
            result = c.fetchone()

            if result and result[0] == user_id:
                # Delete the secret and all associated comments and likes
                c.execute("DELETE FROM Secrets WHERE id = ?", (secret_id,))
                c.execute("DELETE FROM Comments WHERE secret_id = ?", (secret_id,))
                c.execute("DELETE FROM Likes WHERE secret_id = ?", (secret_id,))
                conn.commit()
                await update.message.reply_text(f"Secret #{secret_id} has been deleted.")
            else:
                await update.message.reply_text("You can only delete your own secrets.")

            conn.close()
        else:
            await update.message.reply_text("Please provide the secret ID to delete.")
    except Exception as e:
        print(f"Error deleting secret: {e}")
        await update.message.reply_text("An error occurred while deleting the secret. Please try again later.")

# In the main function
def main():
    application = Application.builder().token(os.getenv("BOT_TOKEN")).build()
    
    # Command Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("view", view))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("delete", delete_secret))
    application.add_handler(CommandHandler("deleteimp", deleteimp))

    # Message Handler for Secrets
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, secret))

    # Callback Query Handlers
    application.add_handler(CallbackQueryHandler(like, pattern=r'^like_'))
    application.add_handler(CallbackQueryHandler(comment, pattern=r'^comment_'))

    # Process comments
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_comment))

    # Run the bot
    application.run_polling()

if __name__ == '__main__':
    main()
