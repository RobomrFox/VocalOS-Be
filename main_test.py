from continuous_recognition import StreamingRecognizer

def main():
    recognizer = StreamingRecognizer()
    try:
        recognizer.start()
    except KeyboardInterrupt:
        recognizer.stop()
        print("Stopped listening.")

if __name__ == "__main__":
    main()
