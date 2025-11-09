import speech_recognition as sr
r = sr.Recognizer()
with sr.Microphone() as source:
    print("🎤 Say 'hello'...")
    r.adjust_for_ambient_noise(source, duration=0.5)
    audio = r.listen(source, timeout=5, phrase_time_limit=4)
print("🧠 Recognizing...")
print(r.recognize_google(audio).lower())
