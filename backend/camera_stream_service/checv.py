import os
import cv2

# Force TCP transport for RTSP in OpenCV
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"

rtsp_url = "rtsp://admin:P%40ssw0rd@192.168.1.64:554/Streaming/channels/101"
cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)

# Optionally, reduce the buffer size
cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)

if not cap.isOpened():
    print("Error: Could not open stream")
else:
    ret, frame = cap.read()
    if ret:
        print("Frame received")
    else:
        print("Error: Could not read frame")
