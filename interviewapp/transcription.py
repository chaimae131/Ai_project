import os
import subprocess
import whisper
import torch
from celery.utils.log import get_task_logger
from sentence_transformers import SentenceTransformer, util
import numpy as np

logger = get_task_logger(__name__)

def extract_audio(video_path, output_audio="temp.wav"):
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Le fichier {video_path} n'existe pas.")
    
    # Convertir la vidéo en audio WAV 16kHz mono
    command = [
        "ffmpeg", "-i", video_path,
        "-vn", "-acodec", "pcm_s16le",
        "-ar", "16000", "-ac", "1",
        output_audio, "-y"
    ]
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Erreur ffmpeg : {e}")
    
    return output_audio

def transcribe_audio(audio_path, model_name="base"):
    # Utiliser GPU si disponible
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Transcription avec Whisper sur {device}...")

    model = whisper.load_model(model_name, device=device)
    result = model.transcribe(audio_path)
    
    return result["text"]

def compare_answers(expected_answer, candidate_answer):
    # Charger le modèle pour la similarité sémantique
    model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    
    # Encoder les réponses
    embedding1 = model.encode(expected_answer, convert_to_tensor=True)
    embedding2 = model.encode(candidate_answer, convert_to_tensor=True)
    
    # Calculer la similarité cosinus
    cosine_scores = util.cos_sim(embedding1, embedding2)
    similarity_score = float(cosine_scores[0][0])  # Convertir en float Python
    
    # Convertir le score en pourcentage (0-100)
    percentage_score = max(0, min(100, (similarity_score + 1) * 50))
    
    return percentage_score

def video_to_text(video_path, expected_answer=None, model_name="base"):
    logger.info(f"Traitement de la vidéo : {video_path}")
    
    audio_path = extract_audio(video_path)
    logger.info("Audio extrait.")

    transcription = transcribe_audio(audio_path, model_name=model_name)
    logger.info("Transcription terminée.")

    # Nettoyer
    if os.path.exists(audio_path):
        os.remove(audio_path)

    # Comparaison avec la réponse attendue si fournie
    similarity_score = None
    if expected_answer:
        similarity_score = compare_answers(expected_answer, transcription)
        logger.info(f"Score de similarité: {similarity_score:.2f}%")

    return {
        "transcription": transcription,
        "similarity_score": similarity_score
    }