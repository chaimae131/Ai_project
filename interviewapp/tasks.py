from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings
from django.core.files.base import ContentFile
from .models import VideoResponse, Interview, InterviewAnalysis
import cv2
import numpy as np
import pandas as pd
from deepface import DeepFace
import os
import matplotlib.pyplot as plt
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import tempfile
import json

from .transcription import video_to_text  # Import de la fonction transcription

logger = get_task_logger(__name__)

@shared_task(bind=True)
def analyze_video_response(self, video_response_id):
    video_response = VideoResponse.objects.get(id=video_response_id)
    
    try:
        emotion_labels = ['angry', 'disgust', 'fear', 'happy', 'sad', 'surprise', 'neutral']
        video_path = video_response.video_file.path
        
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Impossible d'ouvrir la vidéo: {video_path}")
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps
        
        frame_interval = 10
        frame_count = 0
        results = []
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_count += 1
            
            if frame_count % frame_interval != 0:
                continue
            
            try:
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                rgb_frame = preprocess_frame(rgb_frame)
                analysis = analyze_frame(rgb_frame)
                
                if isinstance(analysis, list):
                    analysis = analysis[0]
                
                emotions = {k: float(v) for k, v in analysis['emotion'].items()}
                dominant_emotion = analysis['dominant_emotion']
                stress_score = float(0.5 * emotions['fear'] + 0.3 * emotions['angry'] + 0.2 * emotions['sad'])
                
                results.append({
                    'frame': frame_count,
                    'time': float(frame_count / fps),
                    'dominant_emotion': dominant_emotion,
                    'stress_score': stress_score,
                    **emotions
                })
                
            except Exception as e:
                logger.error(f"Erreur d'analyse sur la frame {frame_count}: {str(e)}")
                continue
        
        cap.release()
        
        if results:
            df_results = pd.DataFrame(results)
            
            # Transcription et comparaison sémantique
            expected_answer = video_response.interview_question.question.expected_answer
            transcription_data = video_to_text(video_path, expected_answer=expected_answer)
            
            analysis_result = {
                'summary': {
                    'duration': float(duration),
                    'total_frames': int(total_frames),
                    'frames_analyzed': len(results),
                    'dominant_emotion_overall': df_results['dominant_emotion'].mode()[0],
                    'avg_stress_score': float(df_results['stress_score'].mean()),
                    'emotion_percentages': {
                        emotion: float(df_results[emotion].mean()) for emotion in emotion_labels
                    },
                    'transcription': transcription_data['transcription'],
                    'similarity_score': transcription_data['similarity_score'],
                },
                'raw_data': json.loads(df_results.to_json(orient='records'))
            }
            
            video_response.analysis_result = analysis_result
            video_response.analysis_completed = True
            video_response.duration = duration
            video_response.save()
            logger.info(f"Analyse terminée pour la vidéo {video_response_id}")
            check_interview_completion.delay(video_response.interview_question.interview.id)
            
            return analysis_result
        else:
            raise ValueError("Aucun visage détecté dans la vidéo")
    
    except Exception as e:
        logger.error(f"Erreur lors de l'analyse de la vidéo {video_response_id}: {str(e)}")
        raise self.retry(exc=e, countdown=60, max_retries=3)

def preprocess_frame(frame):
    height, width = frame.shape[:2]
    if width > 1280 or height > 720:
        scale = min(1280/width, 720/height)
        frame = cv2.resize(frame, (0,0), fx=scale, fy=scale)
    return frame

def analyze_frame(frame):
    backends = ['opencv', 'ssd', 'dlib', 'mtcnn', 'retinaface']
    
    for backend in backends:
        try:
            result = DeepFace.analyze(frame, actions=['emotion'],
                                    enforce_detection=False,
                                    silent=True,
                                    detector_backend=backend)
            if result and (isinstance(result, list) and result[0].get('emotion')):
                return result
        except Exception:
            continue
    
    raise ValueError("Tous les backends de détection ont échoué")

@shared_task
def check_interview_completion(interview_id):
    interview = Interview.objects.get(id=interview_id)
    
    total_questions = interview.questions.count()
    completed_responses = VideoResponse.objects.filter(
        interview_question__interview=interview,
        analysis_completed=True
    ).count()
    
    if total_questions == completed_responses and interview.status == 'C':
        interview.status = 'D'
        interview.save()
        generate_interview_report.delay(interview.id)
        return True
    
    return False

@shared_task(bind=True)
def generate_interview_report(self, interview_id):
    interview = Interview.objects.get(id=interview_id)
    video_responses = VideoResponse.objects.filter(
        interview_question__interview=interview
    ).select_related('interview_question__question')
    
    with tempfile.TemporaryDirectory() as temp_dir:
        pdf_path = os.path.join(temp_dir, f'interview_report_{interview.id}.pdf')
        doc = SimpleDocTemplate(pdf_path, pagesize=letter)
        
        styles = getSampleStyleSheet()
        title_style = styles['Heading1']
        heading_style = styles['Heading2']
        body_style = styles['BodyText']
        small_style = ParagraphStyle(
            'small',
            parent=body_style,
            fontSize=9,
            leading=11
        )
        
        elements = []
        
        elements.append(Paragraph(
            f"Rapport d'analyse d'entretien - { interview.candidate.full_name}",
            title_style
        ))
        elements.append(Spacer(1, 0.25 * inch))
        
        elements.append(Paragraph("Informations générales", heading_style))
        elements.append(Paragraph(
            f"Candidat: {interview.candidate.full_name}",
            body_style
        ))
        elements.append(Paragraph(
            f"Date: {interview.created_at.strftime('%d/%m/%Y %H:%M')}",
            body_style
        ))
        elements.append(Spacer(1, 0.25 * inch))
        
        elements.append(Paragraph("Résumé global", heading_style))
        
        total_stress = 0
        emotion_totals = {emotion: 0 for emotion in ['angry', 'disgust', 'fear', 'happy', 'sad', 'surprise', 'neutral']}
        question_count = 0
        total_similarity = 0
        similarity_count = 0
        
        for response in video_responses:
            if response.analysis_result:
                total_stress += response.analysis_result['summary']['avg_stress_score']
                for emotion, value in response.analysis_result['summary']['emotion_percentages'].items():
                    emotion_totals[emotion] += value
                
                sim_score = response.analysis_result['summary'].get('similarity_score')
                if sim_score is not None:
                    total_similarity += sim_score
                    similarity_count += 1
                
                question_count += 1
        
        if question_count > 0:
            avg_stress = total_stress / question_count
            avg_emotions = {emotion: total / question_count for emotion, total in emotion_totals.items()}
            dominant_emotion = max(avg_emotions.items(), key=lambda x: x[1])[0]
            
            avg_similarity = total_similarity / similarity_count if similarity_count > 0 else None
            
            # Décision finale combinée
            if avg_similarity is not None:
                if avg_stress < 60 and avg_similarity >= 60:
                    interview.result = 'P'
                    result = "Réussi"
                else:
                    interview.result = 'F'
                    result = "Échoué"
            else:
                if avg_stress < 60:
                    interview.result = 'P'
                    result = "Réussi"
                else:
                    interview.result = 'F'
                    result = "Échoué"
            
            interview.save()
            
            elements.append(Paragraph(
                f"Résultat final: <b>{result}</b> (Stress moyen: {avg_stress:.1f}/100"
                + (f", Similarité moyenne: {avg_similarity:.1f}%" if avg_similarity is not None else "") + ")",
                ParagraphStyle(
                    'result',
                    parent=body_style,
                    fontSize=12,
                    textColor='green' if result == "Réussi" else 'red',
                    spaceAfter=20
                )
            ))
            elements.append(Paragraph(
                f"Score de stress moyen: {avg_stress:.1f}/100",
                body_style
            ))
            if avg_similarity is not None:
                elements.append(Paragraph(
                    f"Score de similarité moyen: {avg_similarity:.1f}%",
                    body_style
                ))
            elements.append(Paragraph(
                f"Émotion dominante: {dominant_emotion}",
                body_style
            ))
            elements.append(Spacer(1, 0.1 * inch))
            
            fig, ax = plt.subplots(figsize=(6, 4))
            ax.bar(avg_emotions.keys(), avg_emotions.values())
            ax.set_title('Répartition moyenne des émotions')
            ax.set_ylabel('Pourcentage')
            plt.tight_layout()
            
            chart_path = os.path.join(temp_dir, 'avg_emotions.png')
            plt.savefig(chart_path)
            plt.close()
            
            elements.append(Image(chart_path, width=5*inch, height=3.3*inch))
            elements.append(Spacer(1, 0.25 * inch))
        
        elements.append(Paragraph("Analyse par question", heading_style))
        
        for response in video_responses:
            if not response.analysis_result:
                continue
                
            analysis = response.analysis_result['summary']
            question = response.interview_question.question
            
            elements.append(Paragraph(
                f"Question {response.interview_question.order}: {question.text}",
                body_style
            ))
            elements.append(Paragraph(
                f"Émotion dominante: {analysis['dominant_emotion_overall']}",
                small_style
            ))
            elements.append(Paragraph(
                f"Score de stress: {analysis['avg_stress_score']:.1f}/100",
                small_style
            ))

            if analysis.get('transcription'):
                elements.append(Paragraph("Transcription de la réponse :", body_style))
                elements.append(Paragraph(analysis['transcription'], small_style))
            
            if analysis.get('similarity_score') is not None:
                similarity = analysis['similarity_score']
                color = 'green' if similarity >= 60 else 'red'
                elements.append(Paragraph(
                    f"Score de similarité sémantique : <b>{similarity:.1f}%</b>",
                    ParagraphStyle(
                        'similarity',
                        parent=small_style,
                        textColor=color,
                        spaceAfter=10
                    )
                ))
            
            elements.append(Spacer(1, 0.1 * inch))
            
            df = pd.DataFrame(response.analysis_result['raw_data'])
            fig, ax = plt.subplots(figsize=(6, 3))
            for emotion in ['angry', 'disgust', 'fear', 'happy', 'sad', 'surprise', 'neutral']:
                ax.plot(df['time'], df[emotion], label=emotion)
            ax.plot(df['time'], df['stress_score'], label='Stress', linestyle='--', color='black')
            ax.set_title(f'Évolution des émotions - Q{response.interview_question.order}')
            ax.set_xlabel('Temps (s)')
            ax.set_ylabel('Score')
            ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
            plt.tight_layout()
            
            chart_path = os.path.join(temp_dir, f'emotions_q{response.interview_question.order}.png')
            plt.savefig(chart_path)
            plt.close()
            
            elements.append(Image(chart_path, width=5*inch, height=3*inch))
            elements.append(Spacer(1, 0.25 * inch))
        
        doc.build(elements)
        
        analysis, created = InterviewAnalysis.objects.get_or_create(interview=interview)
        
        with open(pdf_path, 'rb') as pdf_file:
            analysis.overall_report.save(
                f'interview_report_{interview.id}.pdf',
                ContentFile(pdf_file.read())
            )
        
        summary_data = {
            'avg_stress': avg_stress,
            'dominant_emotion': dominant_emotion,
            'emotion_distribution': avg_emotions,
            'questions_analyzed': question_count,
            'avg_similarity': avg_similarity,
        }
        analysis.summary = summary_data
        analysis.save()
        
        return pdf_path
