import os
import uuid
from flask import Flask, request, render_template, send_file
from processor import process_video

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
PROCESSED_FOLDER = "processed"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        file = request.files.get("video")
        if not file:
            return "No file uploaded", 400
        
        file_id = str(uuid.uuid4())[:8]
        raw_path = os.path.join(UPLOAD_FOLDER, f"{file_id}_{file.filename}")
        clean_path = os.path.join(PROCESSED_FOLDER, f"clean_{file_id}_{file.filename}")
        
        file.save(raw_path)
        success = process_video(raw_path, clean_path)
        
        # মূল র ফাইল মুছে স্পেস বাঁচানো
        if os.path.exists(raw_path):
            os.remove(raw_path)

        if success:
            return send_file(clean_path, as_attachment=True)
        return "Processing failed", 500

    return '''
    <!doctype html>
    <title>Video Copyright Modifier</title>
    <h2>Upload Video to Modify & Download</h2>
    <form method=post enctype=multipart/form-data>
      <input type=file name=video required>
      <input type=submit value=Upload & Process>
    </form>
    '''

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
