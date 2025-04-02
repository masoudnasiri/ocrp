import cv2

def check_rtsp_connection(rtsp_url):
    """Checks if an RTSP stream can be opened."""
    cap = cv2.VideoCapture(rtsp_url)

    if cap.isOpened():
        print(f"RTSP stream {rtsp_url} is open.")
        ret, frame = cap.read()
        if ret:
            print("Frame read successfully.")
            cv2.imshow("Test Frame", frame)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
        else:
            print("Error: Could not read frame.")

        cap.release()
        return True
    else:
        print(f"Error: Could not open RTSP stream {rtsp_url}.")
        return False

if __name__ == "__main__":
    rtsp_url = "rtsp://admin:P@ssw0rd@192.168.1.64:554/Streaming/channels/101?tcp" # Replace with your RTSP URL
    check_rtsp_connection(rtsp_url)