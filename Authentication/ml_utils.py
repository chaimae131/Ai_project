import fitz  # Pour lire les PDFs
import re
import pandas as pd
from joblib import load
from sentence_transformers import CrossEncoder, SentenceTransformer
import os
from datetime import datetime
from typing import Dict, List, Optional, Union
import traceback
import torch

# ==============================================
# MODÈLES (Chargement et gestion des modèles)
# ==============================================
class Models:
    def __init__(self):
        """Initialise les modèles pour le traitement et la similarité"""
        print("Initializing models...")
        
        # Chargement du modèle local CrossEncoder
        self.local_model = self._load_local_model()
        print(f"Local model loaded: {self.local_model is not None}")
        
        # Chargement du modèle SentenceTransformer
        try:
            print("Loading SentenceTransformer...")
            self.sentence_transformer = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
            print("SentenceTransformer loaded successfully")
        except Exception as e:
            print(f"Error loading SentenceTransformer: {str(e)}")
            self.sentence_transformer = None

    def _load_local_model(self) -> Optional[CrossEncoder]:
        """Charge le modèle local depuis le fichier"""
        local_model_path = "Authentication\crossencoder"
        if not os.path.exists(local_model_path):
            local_model_path = os.path.join(os.path.dirname(__file__), "crossencoder")
        
        print(f"Looking for local model at: {local_model_path}")
        print(f"Path exists: {os.path.exists(local_model_path)}")
        
        try:
            # Essayer de charger comme un modèle CrossEncoder
            try:
                model = CrossEncoder(local_model_path, device='cpu')
                print(f"Model loaded as CrossEncoder")
                return model
            except Exception as e:
                print(f"Failed to load as CrossEncoder: {str(e)}")
                # Si ça échoue, essayer de charger avec joblib
                model = load(local_model_path)
                print(f"Model type: {type(model)}")
                return model
        except Exception as e:
            print(f"Local model not found or error loading: {str(e)}")
            return None

# ==============================================
# TRAITEMENT DES CVs (Extraction et structuration)
# ==============================================
class CVProcessor:
    @staticmethod
    def extract_sections(cv_text: str) -> Dict[str, str]:
        """Extrait les sections principales d'un CV avec des regex"""
        # Normalisation initiale du texte
        cv_text = re.sub(r'\s+', ' ', cv_text.replace('\n', ' ')).strip()
        print(f"Normalized CV text length: {len(cv_text)}")
        
        section_patterns = {
            'personal_info': r'(?:coord|contact|informations? personnelles?)[\s:]*(.*?)(?=\b(?:exp|formation|compétences)\b|$)',
            'experience': r'(?:expériences? professionnelles?|expérience|work experience|employment history)[\s:]*(.*?)(?=\b(?:formation|education|compétences)\b|$)',
            'education': r'(?:formations?|études|education|academic background)[\s:]*(.*?)(?=\b(?:exp|compétences|skills)\b|$)',
            'skills': r'(?:compétences|skills|competences|technical skills)[\s:]*(.*?)(?=\b(?:exp|projects|formation|langues)\b|$)',
            'soft_skills': r'(?:soft skills|compétences comportementales|compétences interpersonnelles)[\s:]*(.*?)(?=\b(?:exp|formation|skills|langues|projects)\b|$)',
            'languages': r'(?:langues?|languages)[\s:]*(.*?)(?=\b(?:exp|formation|références)\b|$)',
            'projects': r'(?:projets?|projects)[\s:]*(.*?)(?=\b(?:exp|education|formation|compétences)\b|$)'
        }
        
        sections = {
            name: match.group(1).strip() 
            for name, pattern in section_patterns.items() 
            if (match := re.search(pattern, cv_text, re.IGNORECASE))
        } or {'raw_text': cv_text}
        
        print(f"Extracted sections: {list(sections.keys())}")
        return sections

    @staticmethod
    def parse_experience(experience_text: str) -> List[Dict[str, str]]:
        """Structure les expériences professionnelles"""
        entries = [e.strip() for e in re.split(
            r'(?:\d{4}[\s-]*(?:à|au|\-|\–|present|now)[\s-]*\d{4}|•|\- )', 
            experience_text
        ) if e.strip()]
        
        print(f"Parsed {len(entries)} experience entries")
        
        return [{
            'position': (m.group(1).strip() if (m := re.search(r'^(.*?)(?:chez|at|@|,)(.*)', e, re.IGNORECASE)) else e),
            'company': m.group(2).strip() if m else "Non spécifié",
            'start_date': (d.group(1) if (d := re.search(r'(\d{4})\s*(?:à|au|\-|\–)\s*(\d{4}|present|now)', e)) else "Non spécifié"),
            'end_date': d.group(2) if d else "Non spécifié",
            'description': e
        } for e in entries]

    @staticmethod
    def parse_education(education_text: str) -> List[Dict[str, str]]:
        """Structure les formations académiques"""
        entries = [e.strip() for e in re.split(
            r'(?:\d{4}[\s-]*(?:à|au|\-|\–)\s*\d{4}|•|\- )', 
            education_text
        ) if e.strip()]
        
        print(f"Parsed {len(entries)} education entries")
        
        return [{
            'degree': (m.group(1).strip() if (m := re.search(r'^(.*?)(?:à|at|@|,)(.*)', e, re.IGNORECASE)) else e),
            'institution': m.group(2).strip() if m else "Non spécifié",
            'description': e
        } for e in entries]

    @staticmethod
    def extract_skills(skills_text: str) -> List[str]:
        """Extrait et nettoie les compétences techniques"""
        skills = [s.strip() for s in re.split(r'[,;]|\n', skills_text) 
                if s.strip() and len(s.strip()) > 2 and not s.strip().isdigit()]
        
        print(f"Extracted {len(skills)} skills")
        return skills

    @staticmethod
    def process_cv(cv_text: str) -> Dict[str, Union[str, Dict]]:
        """Pipeline complet de traitement d'un CV"""
        print(f"Processing CV text of length: {len(cv_text)}")
        
        sections = CVProcessor.extract_sections(cv_text)
        
        processed = {
            'raw_text': cv_text,
            'sections': {
                'experience': CVProcessor.parse_experience(sections.get('experience', '')),
                'education': CVProcessor.parse_education(sections.get('education', '')),
                'skills': CVProcessor.extract_skills(sections.get('skills', '')),
                **{k: sections[k] for k in ['personal_info', 'languages', 'projects'] if k in sections}
            },
            'processed_at': datetime.now().isoformat(),
            'cleaned_text': CVProcessor.clean_text(
                ' '.join(sections.get(k, '') 
                for k in ['experience', 'skills', 'education'] 
                if k in sections
            ) or cv_text)
        }
        
        print(f"Cleaned text length: {len(processed['cleaned_text'])}")
        return processed

    @staticmethod
    def clean_text(text: str) -> str:
        """Nettoie le texte pour l'analyse"""
        cleaned = re.sub(r'\s+', ' ', re.sub(r'[^a-zA-Z0-9\s]', ' ', text.lower())).strip()
        print(f"Original text length: {len(text)}, Cleaned text length: {len(cleaned)}")
        return cleaned

# ==============================================
# TRAITEMENT DES OFFRES D'EMPLOI
# ==============================================
class JobOfferProcessor:
    @staticmethod
    def process_offer(offer_data: Dict) -> Dict:
        """Structure une offre d'emploi pour l'analyse"""
        print(f"Processing job offer: {offer_data.get('title', 'No title')}")
        
        processed = {
            'title': offer_data.get('title', ''),
            'company': offer_data.get('company', ''),
            'description': CVProcessor.clean_text(offer_data.get('description', '')),
            'requirements': CVProcessor.clean_text(offer_data.get('requirements', '')),
            'location': offer_data.get('location', ''),
            'job_type': offer_data.get('job_type', ''),
            'tags': ', '.join(offer_data.get('tags', [])),
            'comparison_text': ''
        }
        
        # Inclure le titre et les tags dans le texte de comparaison pour une meilleure correspondance
        title_text = CVProcessor.clean_text(processed['title'])
        tags_text = CVProcessor.clean_text(processed['tags'])
        
        # Donner plus de poids aux exigences et aux tags en les répétant
        processed['comparison_text'] = f"{title_text} {processed['description']} {processed['requirements']} {processed['requirements']} {tags_text} {tags_text}"
        
        print(f"Job comparison text length: {len(processed['comparison_text'])}")
        print(f"Job comparison text sample: {processed['comparison_text'][:100]}...")
        
        return processed

# ==============================================
# GESTION DES DONNÉES (CSV et PDF)
# ==============================================
class DataManager:
    @staticmethod
    def extract_text_from_pdf(pdf_path: str) -> str:
        """Extrait le texte brut d'un PDF"""
        print(f"Extracting text from PDF: {pdf_path}")
        print(f"File exists: {os.path.exists(pdf_path)}")
        
        if os.path.exists(pdf_path):
            print(f"File size: {os.path.getsize(pdf_path)} bytes")
        
        try:
            with fitz.open(pdf_path) as doc:
                print(f"PDF opened successfully. Pages: {len(doc)}")
                text = ' '.join(page.get_text() for page in doc)
                print(f"Extracted text length: {len(text)}")
                if len(text) > 0:
                    print(f"Text sample: {text[:100]}...")
                else:
                    print("Warning: Extracted text is empty!")
                return text
        except Exception as e:
            print(f"Error extracting text from PDF: {str(e)}")
            print(traceback.format_exc())
            raise

    @staticmethod
    def save_to_csv(data: Dict, filename: str) -> None:
        """Sauvegarde des données structurées en CSV"""
        pd.DataFrame([data]).to_csv(
            filename, 
            index=False, 
            mode='a', 
            header=not os.path.exists(filename)
        )

# ==============================================
# CALCUL DE SIMILARITÉ
# ==============================================
class SimilarityCalculator:
    def __init__(self, models: Models):
        self.models = models

    def calculate(self, cv_data: Dict, job_data: Dict) -> Dict:
        """Calcule les scores de similarité en utilisant les deux modèles"""
        cv_text = cv_data['cleaned_text']
        job_text = job_data['comparison_text']
        
        print(f"CV text length: {len(cv_text)}")
        print(f"Job text length: {len(job_text)}")
        
        # Initialiser les scores
        st_score = None
        local_score = None
        
        # 1. Calcul avec SentenceTransformer (si disponible)
        if self.models.sentence_transformer:
            try:
                print("Encoding texts with SentenceTransformer...")
                embeddings = self.models.sentence_transformer.encode([cv_text, job_text])
                print(f"Embeddings shape: {embeddings.shape}")
                
                st_score = (embeddings[0] @ embeddings[1].T).item()
                print(f"SentenceTransformer score: {st_score}")
            except Exception as e:
                print(f"Error during SentenceTransformer calculation: {str(e)}")
                print(traceback.format_exc())
                st_score = None
        
        # 2. Calcul avec le modèle local CrossEncoder (si disponible)
        if self.models.local_model:
            try:
                print("Predicting with CrossEncoder model...")
                
                # Essayer différentes méthodes de prédiction
                try:
                    # Avec activation sigmoid
                    score = self.models.local_model.predict([(cv_text, job_text)], 
                                                           activation_fct=torch.sigmoid)[0]
                    print(f"Prediction successful with sigmoid activation")
                except Exception as e1:
                    print(f"Error with sigmoid activation: {str(e1)}")
                    try:
                        # Sans activation
                        score = self.models.local_model.predict([(cv_text, job_text)])[0]
                        print(f"Prediction successful without activation function")
                    except Exception as e2:
                        print(f"Error without activation function: {str(e2)}")
                        
                        # Essayer predict_proba (modèle scikit-learn)
                        try:
                            score = self.models.local_model.predict_proba([cv_text])[0][1]
                            print(f"Prediction successful with predict_proba")
                        except Exception as e3:
                            print(f"Error with predict_proba: {str(e3)}")
                            print("All prediction methods failed, defaulting to None")
                            score = None
                
                # Si on a un score, le normaliser si nécessaire
                if score is not None:
                    if score > 1:
                        score = score / 100  # Si le score est déjà sur 100
                    local_score = score
                    print(f"Local model score: {local_score}")
                
            except Exception as e:
                print(f"Error with local model prediction: {str(e)}")
                print(traceback.format_exc())
                local_score = None
        
        # 3. Calcul du score final (moyenne des scores disponibles)
        scores = [s for s in [st_score, local_score] if s is not None]
        
        if not scores:
            print("WARNING: No scores available, defaulting to 0")
            final_score = 0
        else:
            final_score = sum(scores) / len(scores) * 100
            print(f"Final score (average of {len(scores)} models): {final_score}")
        
        return {
            'cv_id': cv_data.get('id', ''),
            'job_id': job_data.get('id', ''),
            'sentence_transformer_score': round(st_score * 100, 2) if st_score is not None else None,
            'local_model_score': round(local_score * 100, 2) if local_score is not None else None,
            'final_score': round(final_score, 2),
            'calculated_at': datetime.now().isoformat(),
            'models_used': len(scores)
        }

# ==============================================
# FONCTION PRINCIPALE D'ANALYSE CV-OFFRE
# ==============================================
def analyze_cv_job_match(cv_path: str, job_title: str = "", job_description: str = "", job_requirements: str = "", job_tags: List[str] = None) -> float:
    """
    Fonction principale qui encapsule tout le processus d'analyse:
    1. Extraction du texte du CV
    2. Traitement du CV
    3. Traitement de l'offre d'emploi
    4. Calcul du score de similarité
    
    Args:
        cv_path: Chemin vers le fichier PDF du CV
        job_title: Titre du poste (optionnel)
        job_description: Description du poste
        job_requirements: Exigences du poste (optionnel)
        job_tags: Liste des compétences requises (optionnel)
        
    Returns:
        float: Score de similarité entre 0 et 100
    """
    print(f"\n{'='*50}\nStarting CV-Job match analysis\n{'='*50}")
    print(f"CV path: {cv_path}")
    print(f"Job title: {job_title}")
    print(f"Job description length: {len(job_description)}")
    print(f"Job requirements length: {len(job_requirements)}")
    print(f"Job tags: {job_tags}")
    
    try:
        # Initialisation des composants
        print("\nInitializing components...")
        models = Models()
        data_manager = DataManager()
        cv_processor = CVProcessor()
        job_processor = JobOfferProcessor()
        similarity_calc = SimilarityCalculator(models)
        
        # 1. Extraction du texte du CV
        print("\nExtracting CV text...")
        cv_text = data_manager.extract_text_from_pdf(cv_path)
        
        # 2. Traitement du CV
        print("\nProcessing CV...")
        processed_cv = cv_processor.process_cv(cv_text)
        
        # 3. Traitement de l'offre d'emploi
        print("\nProcessing job offer...")
        job_offer = {
            'title': job_title,
            'description': job_description,
            'requirements': job_requirements or "",
            'tags': job_tags or []
        }
        processed_job = job_processor.process_offer(job_offer)
        
        # 4. Calcul du score de similarité
        print("\nCalculating similarity...")
        similarity_result = similarity_calc.calculate(processed_cv, processed_job)
        
        # Retourner le score final
        print(f"\nFinal similarity score: {similarity_result['final_score']}%")
        return similarity_result['final_score']
    
    except Exception as e:
        print(f"\nERROR: Exception during CV-Job match analysis: {str(e)}")
        print(f"Detailed traceback:\n{traceback.format_exc()}")
        return 0.0  # Retourner 0 en cas d'erreur

# Fonctions d'aide pour la compatibilité avec le code existant
def extract_text_from_pdf(pdf_path: str) -> str:
    """Fonction de compatibilité qui appelle DataManager.extract_text_from_pdf"""
    return DataManager.extract_text_from_pdf(pdf_path)

def predict_similarity(cv_text: str, job_text: str) -> float:
    """
    Fonction de compatibilité qui calcule la similarité entre un texte de CV et un texte d'offre
    
    Args:
        cv_text: Texte extrait du CV
        job_text: Texte de l'offre d'emploi
        
    Returns:
        float: Score de similarité entre 0 et 100
    """
    try:
        print("\nPredicting similarity between CV and job texts...")
        print(f"CV text length: {len(cv_text)}")
        print(f"Job text length: {len(job_text)}")
        
        models = Models()
        cv_processor = CVProcessor()
        
        # Nettoyer et préparer les textes
        cleaned_cv_text = cv_processor.clean_text(cv_text)
        cleaned_job_text = cv_processor.clean_text(job_text)
        
        # Créer des structures de données simplifiées
        cv_data = {'cleaned_text': cleaned_cv_text}
        job_data = {'comparison_text': cleaned_job_text}
        
        # Calculer la similarité
        similarity_calc = SimilarityCalculator(models)
        result = similarity_calc.calculate(cv_data, job_data)
        
        print(f"Similarity prediction result: {result['final_score']}%")
        return result['final_score']
    except Exception as e:
        print(f"Error during similarity prediction: {str(e)}")
        print(traceback.format_exc())
        return 0.0

# ==============================================
# POINT D'ENTRÉE PRINCIPAL
# ==============================================
if __name__ == "__main__":
    # Initialisation
    models = Models()
    data_manager = DataManager()
    cv_processor = CVProcessor()
    job_processor = JobOfferProcessor()
    similarity_calc = SimilarityCalculator(models)

    # Exemple: Traitement d'un CV PDF
    cv_text = data_manager.extract_text_from_pdf("mon_cv.pdf")
    processed_cv = cv_processor.process_cv(cv_text)
    data_manager.save_to_csv(processed_cv, "processed_cvs.csv")

    # Exemple: Traitement d'une offre d'emploi
    job_offer = {
        'title': "Développeur Python Senior",
        'company': "TechCorp",
        'description': "Nous recherchons un développeur expérimenté...",
        'requirements': "5+ ans d'expérience en Python, maîtrise de Django...",
        'location': "Paris",
        'job_type': "CDI",
        'tags': ["Python", "Django", "AWS"]
    }
    processed_job = job_processor.process_offer(job_offer)
    data_manager.save_to_csv(processed_job, "processed_jobs.csv")

    # Calcul de similarité
    similarity = similarity_calc.calculate(processed_cv, processed_job)
    print(f"Score de similarité: {similarity['final_score']}%")
    data_manager.save_to_csv(similarity, "similarity_scores.csv")