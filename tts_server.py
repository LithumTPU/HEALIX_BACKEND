from flask import Flask, request, jsonify, send_file, after_this_request, Response
from flask_cors import CORS
import os
import tempfile
import traceback
import math
import struct
import wave
import sys
import uuid

GROQ_API_KEY = "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"

try:
    from groq import Groq
except Exception:
    Groq = None

app = Flask(__name__)
CORS(app)

def generate_fallback_audio(temp_path, text, request_id):
    """Generate fallback audio when TTS service fails"""
    try:
        duration = min(8, max(1, len(text) // 20))
        sample_rate = 16000
        num_samples = duration * sample_rate
        freq = 440.0
        amplitude = 32767 * 0.3
        
        with wave.open(temp_path, 'w') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            for i in range(num_samples):
                val = int(amplitude * math.sin(2 * math.pi * freq * (i / sample_rate)))
                wf.writeframes(struct.pack('<h', val))
        
        print(f"[TTS][{request_id}] Generated fallback WAV ({len(text)} chars)")
        
        return send_file(
            temp_path,
            as_attachment=True,
            download_name='speech.wav',
            mimetype='audio/wav'
        )
    except Exception as fallback_error:
        print(f"[TTS][{request_id}] Fallback also failed: {str(fallback_error)}")
        return jsonify({'error': 'Both TTS and fallback failed'}), 500

@app.route('/api/tts', methods=['POST', 'OPTIONS'])
def api_tts():
    if request.method == 'OPTIONS':
        return '', 200

    data = request.get_json(force=True)
    text = (data or {}).get('text', '')
    voice = (data or {}).get('voice', 'Aaliyah-PlayAI')

    if not text:
        return jsonify({'error': 'no text provided'}), 400

    temp_fd, temp_path = tempfile.mkstemp(suffix='.wav')
    os.close(temp_fd)

    @after_this_request
    def cleanup(response: Response):
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception:
            pass
        return response

    try:
        request_id = uuid.uuid4().hex[:8]
        print(f"[TTS][{request_id}] Received request, chars={len(text)} voice={voice}")
        
        # Check if Groq is available
        if Groq is None:
            print(f"[TTS][{request_id}] Groq library not available, using fallback")
            return generate_fallback_audio(temp_path, text, request_id)
        
        api_key = GROQ_API_KEY
        if not api_key or api_key == "gsk_YOUR_REAL_GROQ_KEY_HERE":
            print(f"[TTS][{request_id}] Invalid API key, using fallback")
            return generate_fallback_audio(temp_path, text, request_id)

        print(f"[TTS][{request_id}] Attempting Groq TTS...")
        client = Groq(api_key=api_key)
        
        try:
            response = client.audio.speech.create(
                model="playai-tts",
                voice=voice,
                response_format="wav",
                input=text,
            )
            
            # **FIXED: Use the .iter_bytes() method on the response object**
            print(f"[TTS][{request_id}] Response type: {type(response)}")
            
            with open(temp_path, "wb") as f:
                # Iterate through chunks using the correct method
                for chunk in response.iter_bytes(): 
                    f.write(chunk)
            
            print(f"[TTS][{request_id}] Successfully saved Groq TTS output")
            
            file_size = os.path.getsize(temp_path)
            print(f"[TTS][{request_id}] Generated WAV via Groq ({len(text)} chars, {file_size} bytes)")
            
            return send_file(
                temp_path,
                as_attachment=True,
                download_name='speech.wav',
                mimetype='audio/wav'
            )
            
        except Exception as groq_error:
            # Note: The original error message "object is not iterable" would appear here.
            print(f"[TTS][{request_id}] Groq API error: {str(groq_error)}")
            return generate_fallback_audio(temp_path, text, request_id)

    except Exception as e:
        tb = traceback.format_exc()
        print(f"[TTS] General error: {tb}")
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'message': 'TTS server running'})

if __name__ == '__main__':
    print("Starting TTS Server...")
    print(f"Python executable: {sys.executable}")
    app.run(host='0.0.0.0', port=5001, debug=False)
