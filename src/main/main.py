  from flask import Flask, render_template, request, session, redirect, url_for
  from flask_socketio import join_room, leave_room, send, SocketIO
  import random
  from string import ascii_uppercase

  app = Flask(__name__)
  app.config["SECRET_KEY"] = "hhhfghs"  # Secret key for Flask session management
  socketio = SocketIO(app)


  class RSAEncryption:
      def __init__(self, p, q):
          self.p = p  # Prime number p
          self.q = q  # Prime number q
          self.public_key, self.private_key = self.generate_keypair()  # Generate RSA keypair

      # Generate RSA keypair
      def generate_keypair(self):
          # Calculate n and phi
          n = self.p * self.q  # n = p * q
          phi = (self.p - 1) * (self.q - 1)  # phi = (p - 1) * (q - 1)

          # Choose a random integer e such that 1 < e < phi and gcd(e, phi) = 1
          e = random.randint(2, phi - 1)
          while self.gcd(e, phi) != 1:
              e = random.randint(2, phi - 1)

          # Calculate d, the modular multiplicative inverse of e modulo phi
          d = self.mod_inverse(e, phi)

          # Return public and private keys
          return (e, n), (d, n)

      # Calculate greatest common divisor
      def gcd(self, a, b):
          while b != 0:
              a, b = b, a % b
          return a

      # Calculate modular multiplicative inverse
      def mod_inverse(self, a, m):
          m0, x0, x1 = m, 0, 1
          while a > 1:
              q = a // m
              m, a = a % m, m
              x0, x1 = x1 - q * x0, x0
          return x1 + m0 if x1 < 0 else x1

      # Encrypt a message using the public key
      def encrypt_message(self, message_plain):
          encrypted_text = [pow(ord(char), self.public_key[0], self.public_key[1]) for char in message_plain]
          return encrypted_text

      # Decrypt a message using the private key
      def decrypt_message(self, encrypted_text):
          decrypted_text = [chr(pow(char, self.private_key[0], self.private_key[1])) for char in encrypted_text]
          return ''.join(decrypted_text)

  # Class for representing a chat room
  class Room:
      def __init__(self, code):
          self.code = code  # Room code
          self.members = 0  # Number of members in the room
          self.messages = []  # List of messages in the room

  # Class for managing the chat application
  class ChatApp:
      def __init__(self):
          self.rooms = {}  # Dictionary to store room information
          self.encryption = RSAEncryption(61, 53)  # Initialize RSA encryption with prime numbers p and q

      # Generate a unique room code
      def generate_unique_code(self, length):
          while True:
              code = "".join(random.choices(ascii_uppercase, k=length))
              if code not in self.rooms:
                  break
          return code

      # Handle incoming message
      def handle_message(self, data, room):
          # Encrypt the message
          encrypted_message = self.encryption.encrypt_message(data["data"])
          # Decrypt immediately for broadcasting
          decrypted_message = self.encryption.decrypt_message(encrypted_message)
          content = {"name": session.get("name"), "message": decrypted_message}
          # Send decrypted message to users in the room
          send(content, to=room)
          # Store original encrypted message for record-keeping
          room.messages.append({"name": session.get("name"), "message": encrypted_message})
          print(f"{session.get('name')} said: {decrypted_message}")

      # Join a room
      def join_room(self, room, name):
          if room not in self.rooms:
              leave_room(room)
              return False
          join_room(room)
          send({"name": name, "message": "has entered the room"}, to=room)
          self.rooms[room].members += 1
          print(f"{name} joined room {room}")
          return True

      # Leave a room
      def leave_room(self, room, name):
          leave_room(room)
          if room in self.rooms:
              self.rooms[room].members -= 1
              if self.rooms[room].members <= 0:
                  del self.rooms[room]
          send({"name": name, "message": "has left the room"}, to=room)
          print(f"{name} has left the room {room}")

  # Instantiate the ChatApp class
  chat_app = ChatApp()

  # Route for home page
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
              room = chat_app.generate_unique_code(4)
              chat_app.rooms[room] = Room(room)
          elif code not in chat_app.rooms:
              return render_template("home.html", error="Room does not exist.", code=code, name=name)

          session["room"] = room
          session["name"] = name
          return redirect(url_for("room"))

      return render_template("home.html")

  # Route for room page
  @app.route("/room")
  def room():
      room_code = session.get("room")
      if room_code is None or session.get("name") is None or room_code not in chat_app.rooms:
          return redirect(url_for("home"))

      return render_template("room.html", code=room_code)

  # Socket.io event handler for receiving messages
  @socketio.on("message")
  def message(data):
      room = session.get("room")
      if room not in chat_app.rooms:
          return
      chat_app.handle_message(data, room)

  # Socket.io event handler for connecting to a room
  @socketio.on("connect")
  def connect(auth):
      room = session.get("room")
      name = session.get("name")
      if not room or not name:
          return
      if not chat_app.join_room(room, name):
          return redirect(url_for("home"))

  # Socket.io event handler for disconnecting from a room
  @socketio.on("disconnect")
  def disconnect():
      room = session.get("room")
      name = session.get("name")
      if room:
          chat_app.leave_room(room, name)

  # Run the application
  if __name__ == "__main__":
      socketio.run(app, debug=True)
