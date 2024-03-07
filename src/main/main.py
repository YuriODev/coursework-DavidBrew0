from flask import Flask, render_template, request, session, redirect, url_for
from flask_socketio import join_room, leave_room, send, SocketIO
import random
from string import ascii_uppercase
from cryptography.fernet import Fernet
app = Flask(__name__)
app.config["SECRET_KEY"] = "hhhfghs"
socketio = SocketIO(app)

key = Fernet.generate_key()
cipher_suite = Fernet(key)

rooms = {}

def generate_unique_code(length):
    while True:
        code = ""
        for _ in range(length):
            code += random.choice(ascii_uppercase)
        if code not in rooms:
            break
    return code

def encrypt_message(message_plain):
    # """Encrypts a message."""
    if isinstance(message_plain, str):
        message_plain = message_plain.encode()
    encrypted_text = cipher_suite.encrypt(message_plain)
    return encrypted_text.decode()

def decrypt_message(encrypted_text):
    #"""Decrypts an encrypted message."""
    decrypted_text = cipher_suite.decrypt(encrypted_text.encode()).decode("utf-8")
    return decrypted_text

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

@app.route("/room")
def room():
    room = session.get("room")
    if room is None or session.get("name") is None or room not in rooms:
        return redirect(url_for("home"))

    decrypted_messages = [{"name": msg["name"], "message": decrypt_message(msg["message"])} for msg in rooms[room]["messages"]]
    return render_template("room.html", code=room, messages=decrypted_messages)

@socketio.on("message")
def message(data):
    room = session.get("room")
    if room not in rooms:
        return

    # Encrypt the message for storage
    encrypted_message = encrypt_message(data["data"])
    # Decrypt immediately for broadcasting
    decrypted_message = decrypt_message(encrypted_message)

    # Prepare the content with the decrypted message for broadcast
    content = {
        "name": session.get("name"),
        "message": decrypted_message  # Sending decrypted message
    }

    # Send decrypted message to users in the room
    send(content, to=room)

    # Store the original encrypted message for record-keeping
    rooms[room]["messages"].append({"name": session.get("name"), "message": encrypted_message})

    print(f"{session.get('name')} said: {decrypted_message}")

@socketio.on("connect")
def connect(auth):
    room = session.get("room")
    name = session.get("name")
    if not room or not name:
        return
    if room not in rooms:
        leave_room(room)
        return

    join_room(room)
    send({"name": name, "message": "has entered the room"}, to=room)
    rooms[room]["members"] += 1
    print(f"{name} joined room {room}")

@socketio.on("disconnect")
def disconnect():
    room = session.get("room")
    name = session.get("name")
    leave_room(room)

    if room in rooms:
        rooms[room]["members"] -= 1
        if rooms[room]["members"] <= 0:
            del rooms[room]

    send({"name": name, "message": "has left the room"}, to=room)
    print(f"{name} has left the room {room}")

if __name__ == "__main__":
    socketio.run(app, debug=True)