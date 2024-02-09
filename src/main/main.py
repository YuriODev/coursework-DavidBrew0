from flask import Flask,render_template, request, session, redirect
from flask_socketio import join_room, leave_room, SocketIO
import random
from string import ascii_uppercase
from Cryptodome.PublicKey import RSA
from Cryptodome.Cipher import PKCS1_OAEP

app = Flask(__name__)
app.config["SECRET_KEY"] = "secret"
socketio = SocketIO(app)

rooms = {}
user_sessions = {}  # New: Mapping of usernames to session IDs
user_keys = {}  # New: Storage for user keys

# Generate a unique room code
def generate_unique_code(length):
    while True:
        code = ""
        for _ in range(length):
            code += random.choice(ascii_uppercase)

        if code not in rooms:
            break

    return code

# Handle the home route
@app.route("/", methods=["POST", "GET"])
def home():
    session.clear()
    if request.method == "POST":
        name = request.form.get("name")
        code = request.form.get("code")
        join = request.form.get("join", False)
        create = request.form.get("create", False)

        if not name:
            return render_template("home.html", error="Please enter a name.", code=code, name=name)

        if join != False and not code:
            return render_template("home.html", error="Please enter a room code.", code=code, name=name)

        room = code
        if create != False:
            room = generate_unique_code(4)
            rooms[room] = {"members": 0, "messages": []}
        elif code not in rooms:
            return render_template("home.html", error="Room does not exist.", code=code, name=name)

        session["room"] = room
        session["name"] = name
        return redirect(url_for("room"))

    return render_template("home.html")

# Handle the room route
@app.route("/room")
def room():
    room = session.get("room")
    if room is None or session.get("name") is None or room not in rooms:
        return redirect(url_for("home"))

    return render_template("room.html", code=room, messages=rooms[room]["messages"])


@socketio.on("message")
def message(data):
    room = session.get("room")
    sender_name = session.get("name")
    if room not in rooms:
        return
    for participant in rooms[room]['participants']:
        if participant == sender_name:
            continue  # Skip the sender
        recipient_sid = user_sessions.get(participant)
        if recipient_sid:
            recipient_public_key = get_public_key(participant)
            encrypted_message = encrypt_message(data["data"], recipient_public_key)
            send({'name': sender_name, 'message': encrypted_message}, room=recipient_sid)
    participants = [participant for participant in rooms[room]["participants"] if participant != sender_name]
    for participant in participants:
        # For each participant, encrypt the message with their public key
        recipient_public_key = get_public_key(participant)
        encrypted_message = encrypt_message(data["data"], recipient_public_key)
        # Create a unique message content for each participant
        content = {
            "name": sender_name,
            "encrypted_message": encrypted_message,  # Sending encrypted message
            # You may need to send additional data like a message ID or encryption metadata
        }
        # Send encrypted message to the participant
        # You might need to adjust this part based on how you manage sending messages to specific users
        send(content, to=participant)
    # Optionally, store or log the original message securely on the server for auditing or history
    print(f"{sender_name} sent an encrypted message in room {room}")


# Handle the connection event
@socketio.on('connect')
def on_connect():
    username = session.get('name')
    # Map the current user's session ID to their username
    user_sessions[username] = request.sid
    # Generate and store keys if not already present
    if username not in user_keys:
        generate_keys(username)

    join_room(room)
    send({"name": name, "message": "has entered the room"}, to=room)  # You need to define the send function to handle sending messages
    rooms[room]["members"] += 1  # Increase the member count of the room
    print(f"{name} joined room {room}")  # Print the join message to the console

# Handle the disconnection event
@socketio.on("disconnect")
def disconnect():
    room = session.get("room")
    name = session.get("name")
    leave_room(room)  # Leave the room

    if room in rooms:
        rooms[room]["members"] -= 1  # Decrease the member count of the room
        if rooms[room]["members"] <= 0:
            del rooms[room]  # Remove the room if there are no members left

    send({"name": name, "message": "has left the room"}, to=room)  # You need to define the send function to handle sending messages
    print(f"{name} has left the room {room}")  # Print the leave message to the console

# Simulated storage for user keys
user_keys = {}

def generate_keys(user_name):
    key = RSA.generate(2048)
    private_key = key.export_key()
    public_key = key.publickey().export_key()
    user_keys[user_name] = {"public_key": public_key, "private_key": private_key}

def get_public_key(user_name):
    return user_keys[user_name]["public_key"]

def get_private_key(user_name):
    return user_keys[user_name]["private_key"]


def encrypt_message(message, public_key):
  recipient_key = RSA.import_key(public_key)
  cipher_rsa = PKCS1_OAEP.new(recipient_key)
  encrypted_message = cipher_rsa.encrypt(message.encode('utf-8'))
  return encrypted_message

def decrypt_message(encrypted_message, private_key):
  key = RSA.import_key(private_key)
  cipher_rsa = PKCS1_OAEP.new(key)
  decrypted_message = cipher_rsa.decrypt(encrypted_message)
  return decrypted_message.decode('utf-8')

# Run the application
if __name__ == "__main__":
    socketio.run(app, port=5000, debug=True)  # Run the app on port 5000 with debug mode enabled
