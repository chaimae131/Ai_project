from django.core.cache import cache
from sentence_transformers import SentenceTransformer, util
import re
import logging
import requests
from bs4 import BeautifulSoup
from django.db.models import Q
from .models import TestQuestion
from django.db.models import Q
import random
import logging
from .models import TestQuestion, Skill


# Charger le modèle (avec cache)
def get_model():
    model = cache.get('sentence_model')
    if model is None:
        model = SentenceTransformer('all-MiniLM-L6-v2')
        cache.set('sentence_model', model, timeout=None)
    return model

def normalize_text(text):
    """Nettoyer le texte pour comparaison."""
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()
  
def compare_answers(user_answer, correct_answer):
    """Compare deux réponses avec similarité cosinus + bonus mots-clés."""
    model = get_model()
    
    # Normalisation
    user_norm = normalize_text(user_answer)
    correct_norm = normalize_text(correct_answer)
    
    # Similarité sémantique
    embeddings = model.encode([user_norm, correct_norm], convert_to_tensor=True)
    score = util.pytorch_cos_sim(embeddings[0], embeddings[1]).item()
    
    # Bonus mots-clés (ex: extraire les noms propres/noms techniques)
    keywords = extract_technical_keywords(correct_norm)  # Nouvelle fonction à créer
    matched = sum(1 for kw in keywords if kw in user_norm.split())
    
    if keywords:
        score += min(matched / len(keywords) * 0.15, 0.15)  # Bonus max +15%
    
    return min(score, 1.0)  # Cap à 100%
  
def extract_technical_keywords(text):
    """Extrait les mots-clés techniques d'une réponse."""
    stopwords = {'the', 'and', 'for', 'this', 'that', 'which'}
    words = set(normalize_text(text).split())
    
    return [w for w in words if (
        len(w) > 3 and 
        w not in stopwords and
        not w.isdigit() and
        w.isalpha()
    )]

def evaluate_qcm_response(user_choice, correct_answer):
    """Évalue une réponse QCM."""
    return {
        'is_correct': user_choice.lower() == correct_answer.lower(),
        'score': 4 if user_choice.lower() == correct_answer.lower() else 0,
        'correct_answer': correct_answer
    }

def evaluate_open_response(user_answer, model_answer):
    """Évalue une réponse ouverte avec scoring intelligent."""
    similarity = compare_answers(user_answer, model_answer)
    points = calculate_points(similarity, user_answer, model_answer)
    
    return {
        'similarity': similarity,
        'score': points,
        'model_answer': model_answer
    }

def calculate_points(similarity, user_answer, correct_answer):
    """Convertit la similarité en points sur 4."""
    user_len = len(user_answer.split())
    correct_len = len(correct_answer.split())
    
    if similarity >= 0.8:   return 4
    elif similarity >= 0.6: return 3
    elif similarity >= 0.4: return 2
    elif similarity >= 0.2: return 1
    else:                   return 0


"""Génération de questions"""
  # Votre fonction de scraping existante

def generate_questions_for_skill(skill_name, num_qcm=3, num_open=2):
    """
    Génère des questions en combinant 3 sources par ordre de priorité :
    1. Base de données
    2. Scraping (si échec BD)
    3. Fallback local (si échec scraping)
    """
    try:
        skill = Skill.objects.get(name__iexact=skill_name)
        
        # 1. Essayer la base de données en premier
        db_questions = get_db_questions(skill, num_qcm, num_open)
        qcm_from_db = [q for q in db_questions if q.question_type == 'QCM']
        open_from_db = [q for q in db_questions if q.question_type == 'OPEN']
        
        # Calcul des manquants
        missing_qcm = max(0, num_qcm - len(qcm_from_db))
        missing_open = max(0, num_open - len(open_from_db))

        # 2. Si manque, essayer le scraping
        scraped_questions = []
        if missing_qcm > 0 or missing_open > 0:
            try:
                scraped = scrape_french_questions(skill_name)
                scraped_questions = process_scraped_questions(scraped, skill, missing_qcm, missing_open)
                
                # Mise à jour des compteurs après scraping
                qcm_from_scraping = [q for q in scraped_questions if q.question_type == 'QCM']
                open_from_scraping = [q for q in scraped_questions if q.question_type == 'OPEN']
                
                missing_qcm = max(0, missing_qcm - len(qcm_from_scraping))
                missing_open = max(0, missing_open - len(open_from_scraping))
                
            except Exception as e:
                logging.warning(f"Échec scraping pour {skill_name}: {str(e)}")

        # 3. Si toujours manquant, utiliser le fallback
        fallback_questions = []
        if missing_qcm > 0 or missing_open > 0:
            fallback_questions = get_fallback_questions(skill_name, missing_qcm, missing_open, skill)

        # Combinaison finale
        final_questions = (
            qcm_from_db + 
            open_from_db + 
            scraped_questions + 
            fallback_questions
        )
        
        # Mélange tout en gardant un équilibre QCM/ouvertes
        random.shuffle(final_questions)
        return final_questions[:num_qcm + num_open]

    except Skill.DoesNotExist:
        # Si la compétence n'existe pas, utiliser scraping + fallback
        return get_non_db_questions(skill_name, num_qcm, num_open)

def get_db_questions(skill, num_qcm, num_open):
    """Récupère les questions depuis la base de données"""
    return list(TestQuestion.objects.filter(
        skill=skill,
        #is_active=True
    ).order_by('?')[:num_qcm + num_open])

def process_scraped_questions(scraped_data, skill, needed_qcm, needed_open):
    """Transforme les données scrapées en objets TestQuestion"""
    questions = []
    for item in scraped_data:
        if needed_qcm > 0 and 'options' in item:  # Si c'est un QCM
            questions.append(TestQuestion(
                text=item['question'],
                question_type='QCM',
                skill=skill,
                option_a=item['options'][0],
                option_b=item['options'][1],
                option_c=item['options'][2],
                option_d=item['options'][3],
                correct_answer=item['answer'],
                is_scraped=True
            ))
            needed_qcm -= 1
        elif needed_open > 0:  # Question ouverte
            questions.append(TestQuestion(
                text=item['question'],
                question_type='OPEN',
                skill=skill,
                model_answer=item['answer'],
                is_scraped=True
            ))
            needed_open -= 1
            
        if needed_qcm == 0 and needed_open == 0:
            break
    return questions

def get_non_db_questions(skill_name, num_qcm, num_open):
    """Combine scraping et fallback quand la compétence n'existe pas en BD"""
    questions = []
    
    # Essayer d'abord le scraping
    try:
        scraped = scrape_french_questions(skill_name)
        skill = Skill(name=skill_name)  # Objet temporaire
        questions = process_scraped_questions(scraped, skill, num_qcm, num_open)
    except Exception as e:
        logging.warning(f"Échec scraping pour {skill_name}: {str(e)}")
    
    # Compléter avec le fallback si nécessaire
    remaining_qcm = max(0, num_qcm - len([q for q in questions if q.question_type == 'QCM']))
    remaining_open = max(0, num_open - len([q for q in questions if q.question_type == 'OPEN']))
    
    if remaining_qcm > 0 or remaining_open > 0:
        questions.extend(get_fallback_questions(skill_name, remaining_qcm, remaining_open, skill))
    
    return questions[:num_qcm + num_open]

def get_fallback_questions(skill_name, num_qcm, num_open, skill=None):
    """Récupère les questions de secours localement"""
    if skill is None:
        skill = Skill(name=skill_name)  # Objet temporaire
    
    skill_lower = skill_name.lower()
    questions = []
    
    # QCM depuis le fallback
    qcm_pool = LOCAL_QCM.get(skill_lower, [])
    for q in random.sample(qcm_pool, min(num_qcm, len(qcm_pool))):
        questions.append(TestQuestion(
            text=q['question'],
            question_type='QCM',
            skill=skill,
            option_a=q['options'][0],
            option_b=q['options'][1],
            option_c=q['options'][2],
            option_d=q['options'][3],
            correct_answer=q['answer'],
            #is_fallback=True
        ))
    
    # Questions ouvertes depuis le fallback
    open_pool = FRENCH_OPEN_QUESTIONS.get(skill_lower, [])
    for q in random.sample(open_pool, min(num_open, len(open_pool))):
        questions.append(TestQuestion(
            text=q['question'],
            question_type='OPEN',
            skill=skill,
            model_answer=q['answer'],
            #is_fallback=True
        ))
    
    return questions
def scrape_french_questions(skill_name, max_questions=6):
    """Scrape des questions techniques en français depuis GeeksforGeeks"""
    try:
        formatted_skill = skill_name.lower().replace(" ", "-")
        url = f"https://www.geeksforgeeks.org/fr/{formatted_skill}-interview-questions/"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7"
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()  # Lève une exception pour les codes 4xx/5xx
        soup = BeautifulSoup(response.text, 'html.parser')

        questions = []
        ignored_keywords = ["préparer", "cliquez", "visitez", "guide", "comment postuler"]
        
        # Cibler les éléments contenant les questions
        candidates = soup.find_all(['h2', 'h3', 'h4', 'strong'])
        
        for candidate in candidates:
            question_text = candidate.get_text().strip()
            
            # Validation de la question
            if (not question_text.endswith('?') or 
                len(question_text.split()) < 5 or
                any(bad in question_text.lower() for bad in ignored_keywords)):
                continue
            
            # Extraction de la réponse
            answer_parts = []
            next_elem = candidate.next_sibling
            
            while next_elem and next_elem.name not in ['h2', 'h3', 'h4', 'strong']:
                if next_elem.name == 'p':
                    text = next_elem.get_text().strip()
                    if len(text) > 20:  # Ignorer les paragraphes trop courts
                        answer_parts.append(text)
                elif next_elem.name == 'ul':
                    for li in next_elem.find_all('li'):
                        answer_parts.append(li.get_text().strip())
                
                next_elem = next_elem.next_sibling
            
            # Nettoyage de la réponse
            answer = ' '.join(answer_parts)
            answer = re.sub(r'\s+', ' ', answer).strip()
            
            if not answer:
                answer = "Répondez selon vos connaissances."
            
            questions.append({
                "question": question_text,
                "answer": answer[:2000]  # Limiter la longueur
            })
            
            if len(questions) >= max_questions:
                break
        
        # Fallback si peu de questions trouvées
        if len(questions) < 3:
            questions.extend(get_fallback_questions(skill_name, max_questions - len(questions)))
        
        return questions[:max_questions]
        
    except requests.RequestException as e:
        logging.error(f"Erreur réseau pour {skill_name}: {str(e)}")
    except Exception as e:
        logging.error(f"Erreur inattendue pour {skill_name}: {str(e)}")
    
    return get_fallback_questions(skill_name, max_questions)

  
  
### ------------- Base locale QCM (FR) ------------- ###

LOCAL_QCM = {
    "python": [
        {
            "question": "Quel est le résultat de print(type([])) en Python ?",
            "options": ["a) <class 'list'>", "b) <class 'tuple'>", "c) <class 'dict'>", "d) <class 'set'>"],
            "answer": "a"
        },
        {
            "question": "Comment définit-on une fonction en Python ?",
            "options": ["a) function myFunc():", "b) def myFunc():", "c) func myFunc():", "d) create myFunc():"],
            "answer": "b"
        },
        {
            "question": "Quelle structure de données Python utilise des paires clé-valeur ?",
            "options": ["a) liste", "b) tuple", "c) dictionnaire", "d) ensemble"],
            "answer": "c"
        },
        {
            "question": "Quel mot-clé est utilisé pour gérer les exceptions en Python ?",
            "options": ["a) try", "b) exception", "c) catch", "d) handle"],
            "answer": "a"
        },
        {
            "question": "Comment insérer un commentaire en Python ?",
            "options": ["a) // commentaire", "b) <!-- commentaire -->", "c) # commentaire", "d) /* commentaire */"],
            "answer": "c"
        },
        {
            "question": "Quel opérateur est utilisé pour l'exponentiation en Python ?",
            "options": ["a) ^", "b) **", "c) pow", "d) exp"],
            "answer": "b"
        }
    ],
    "sql": [
        {
            "question": "Quelle commande SQL sélectionne toutes les colonnes d'une table ?",
            "options": ["a) SELECT *", "b) SELECT ALL", "c) SELECT COLUMNS", "d) SELECT EVERY"],
            "answer": "a"
        },
        {
            "question": "Que fait 'JOIN' en SQL ?",
            "options": ["a) Fusionne deux tables", "b) Supprime une table", "c) Met à jour une table", "d) Crée une table"],
            "answer": "a"
        },
        {
            "question": "Quelle clause SQL limite le nombre de résultats ?",
            "options": ["a) LIMIT", "b) RESTRICT", "c) STOP", "d) END"],
            "answer": "a"
        },
        {
            "question": "Quelle commande ajoute une nouvelle ligne dans une table ?",
            "options": ["a) ADD", "b) INSERT INTO", "c) NEW ROW", "d) APPEND"],
            "answer": "b"
        },
        {
            "question": "Qu'est-ce qu'une clé primaire en SQL ?",
            "options": ["a) Une colonne qui identifie chaque ligne de façon unique", "b) Une référence de clé étrangère", "c) Une colonne avec des valeurs NULL", "d) Une clé de sauvegarde"],
            "answer": "a"
        },
        {
            "question": "Quelle clause est utilisée pour filtrer les enregistrements ?",
            "options": ["a) WHERE", "b) IF", "c) FILTER", "d) SELECT"],
            "answer": "a"
        }
    ],
    "html": [
        {
            "question": "Quel élément HTML représente un paragraphe ?",
            "options": ["a) <p>", "b) <div>", "c) <span>", "d) <section>"],
            "answer": "a"
        },
        {
            "question": "Quelle balise est utilisée pour créer un lien hypertexte ?",
            "options": ["a) <link>", "b) <a>", "c) <href>", "d) <url>"],
            "answer": "b"
        },
        {
            "question": "Comment inclure une image en HTML ?",
            "options": ["a) <image>", "b) <img>", "c) <pic>", "d) <src>"],
            "answer": "b"
        },
        {
            "question": "Que contient la balise <head> ?",
            "options": ["a) Contenu visible", "b) Métadonnées", "c) Informations de pied de page", "d) Uniquement des scripts"],
            "answer": "b"
        },
        {
            "question": "Quelle balise crée une liste à puces ?",
            "options": ["a) <ol>", "b) <li>", "c) <ul>", "d) <dl>"],
            "answer": "c"
        },
        {
            "question": "Quel attribut définit la destination d'un lien ?",
            "options": ["a) src", "b) href", "c) link", "d) target"],
            "answer": "b"
        }
    ],
    "css": [
        {
            "question": "Comment changer la couleur du texte en CSS ?",
            "options": ["a) text-color", "b) color", "c) font-color", "d) text-style"],
            "answer": "b"
        },
        {
            "question": "Quelle propriété contrôle la taille de la police en CSS ?",
            "options": ["a) font-size", "b) text-size", "c) font-style", "d) size"],
            "answer": "a"
        },
        {
            "question": "Comment appliquer un style à tous les éléments <p> ?",
            "options": ["a) .p {}", "b) #p {}", "c) p {}", "d) all.p {}"],
            "answer": "c"
        },
        {
            "question": "Quelle propriété CSS définit la couleur de fond ?",
            "options": ["a) background", "b) bg-color", "c) background-color", "d) color-bg"],
            "answer": "c"
        },
        {
            "question": "Comment centrer horizontalement du texte en CSS ?",
            "options": ["a) text-align: middle;", "b) align: center;", "c) text-align: center;", "d) justify: center;"],
            "answer": "c"
        },
        {
            "question": "Quel sélecteur cible un élément avec l'ID 'main' ?",
            "options": ["a) .main", "b) #main", "c) main", "d) *main"],
            "answer": "b"
        }
    ],
    "javascript": [
        {
            "question": "Comment déclare-t-on une variable en JavaScript (ES6) ?",
            "options": ["a) var x;", "b) let x;", "c) int x;", "d) dim x;"],
            "answer": "b"
        },
        {
            "question": "Quelle méthode ajoute un élément à la fin d'un tableau ?",
            "options": ["a) push()", "b) pop()", "c) shift()", "d) unshift()"],
            "answer": "a"
        },
        {
            "question": "Quelle fonction convertit une chaîne JSON en objet ?",
            "options": ["a) JSON.parse()", "b) JSON.stringify()", "c) JSON.convert()", "d) parseJSON()"],
            "answer": "a"
        },
        {
            "question": "Quel est le résultat de 'typeof null' en JavaScript ?",
            "options": ["a) 'null'", "b) 'object'", "c) 'undefined'", "d) 'boolean'"],
            "answer": "b"
        },
        {
            "question": "Quel opérateur vérifie la valeur et le type ?",
            "options": ["a) ==", "b) =", "c) ===", "d) ~="],
            "answer": "c"
        },
        {
            "question": "Que signifie NaN ?",
            "options": ["a) Not a Name", "b) Not a Node", "c) Not a Number", "d) Not a Null"],
            "answer": "c"
        }
    ],
    "linux": [
        {
            "question": "Quelle commande affiche le contenu d'un fichier sous Linux ?",
            "options": ["a) show", "b) cat", "c) display", "d) open"],
            "answer": "b"
        },
        {
            "question": "Quelle commande modifie les permissions d'un fichier ?",
            "options": ["a) chmod", "b) chperm", "c) chown", "d) permchange"],
            "answer": "a"
        },
        {
            "question": "Quelle commande affiche les processus en cours ?",
            "options": ["a) ps", "b) proc", "c) top", "d) jobs"],
            "answer": "a"
        },
        {
            "question": "Quelle commande permet de changer le propriétaire d'un fichier ?",
            "options": ["a) chown", "b) chmod", "c) chattr", "d) changeowner"],
            "answer": "a"
        },
        {
            "question": "Comment lister les fichiers d'un répertoire ?",
            "options": ["a) dir", "b) ls", "c) list", "d) show"],
            "answer": "b"
        },
        {
            "question": "Quelle commande permet de rechercher du texte dans un fichier ?",
            "options": ["a) find", "b) locate", "c) search", "d) grep"],
            "answer": "d"
        }
    ],
    "networking": [
        {
            "question": "Quel protocole est utilisé pour transmettre des pages web ?",
            "options": ["a) FTP", "b) HTTP", "c) SMTP", "d) SSH"],
            "answer": "b"
        },
        {
            "question": "Que signifie IP ?",
            "options": ["a) Internet Provider", "b) Internet Protocol", "c) Internal Process", "d) Inter Protocol"],
            "answer": "b"
        },
        {
            "question": "Quelle commande permet de tester la connectivité réseau ?",
            "options": ["a) ping", "b) trace", "c) testnet", "d) conncheck"],
            "answer": "a"
        },
        {
            "question": "Quel port est utilisé par HTTPS ?",
            "options": ["a) 21", "b) 80", "c) 443", "d) 22"],
            "answer": "c"
        },
        {
            "question": "Quel est le masque de sous-réseau par défaut pour un réseau de classe C ?",
            "options": ["a) 255.255.0.0", "b) 255.255.255.0", "c) 255.0.0.0", "d) 255.255.254.0"],
            "answer": "b"
        },
        {
            "question": "Quel outil affiche le chemin des paquets vers un hôte ?",
            "options": ["a) ping", "b) netstat", "c) traceroute", "d) pathping"],
            "answer": "c"
        }
    ],
    "git": [
        {
            "question": "Quelle commande initialise un nouveau dépôt Git ?",
            "options": ["a) git init", "b) git start", "c) git create", "d) git new"],
            "answer": "a"
        },
        {
            "question": "Quelle commande récupère et fusionne les modifications du dépôt distant ?",
            "options": ["a) git pull", "b) git fetch", "c) git clone", "d) git push"],
            "answer": "a"
        },
        {
            "question": "Quelle commande crée une nouvelle branche ?",
            "options": ["a) git branch", "b) git checkout", "c) git newbranch", "d) git createbranch"],
            "answer": "a"
        },
        {
            "question": "Quelle commande ajoute des modifications à l'index ?",
            "options": ["a) git stage", "b) git add", "c) git push", "d) git commit"],
            "answer": "b"
        },
        {
            "question": "Quelle commande affiche l'historique des commits ?",
            "options": ["a) git status", "b) git show", "c) git log", "d) git history"],
            "answer": "c"
        },
        {
            "question": "Quelle commande annule les modifications dans le répertoire de travail ?",
            "options": ["a) git reset", "b) git undo", "c) git revert", "d) git checkout -- <file>"],
            "answer": "d"
        }
    ],
    "docker": [
        {
            "question": "Quelle commande liste les conteneurs Docker actifs ?",
            "options": ["a) docker ps", "b) docker list", "c) docker ls", "d) docker active"],
            "answer": "a"
        },
        {
            "question": "Comment construire une image Docker à partir d'un Dockerfile ?",
            "options": ["a) docker build", "b) docker create", "c) docker make", "d) docker image"],
            "answer": "a"
        },
        {
            "question": "Quelle commande démarre un conteneur Docker ?",
            "options": ["a) docker start", "b) docker run", "c) docker go", "d) docker execute"],
            "answer": "b"
        },
        {
            "question": "Quel fichier définit les instructions pour construire une image Docker ?",
            "options": ["a) Dockerfile", "b) docker-compose.yml", "c) build.txt", "d) image.conf"],
            "answer": "a"
        },
        {
            "question": "Quelle commande supprime un conteneur Docker ?",
            "options": ["a) docker delete", "b) docker remove", "c) docker rm", "d) docker clean"],
            "answer": "c"
        },
        {
            "question": "Quelle commande affiche les logs d'un conteneur en cours d'exécution ?",
            "options": ["a) docker logs", "b) docker output", "c) docker tail", "d) docker status"],
            "answer": "a"
        }
    ],
    "aws": [
        {
            "question": "Quel service AWS est utilisé pour le stockage d'objets ?",
            "options": ["a) EC2", "b) S3", "c) RDS", "d) Lambda"],
            "answer": "b"
        },
        {
            "question": "Quel service AWS permet d'exécuter du code sans serveur ?",
            "options": ["a) EC2", "b) Lambda", "c) ECS", "d) S3"],
            "answer": "b"
        },
        {
            "question": "Quel service AWS est une base de données relationnelle ?",
            "options": ["a) S3", "b) RDS", "c) DynamoDB", "d) CloudFront"],
            "answer": "b"
        },
        {
            "question": "Quel service fournit une capacité de calcul évolutive ?",
            "options": ["a) S3", "b) EC2", "c) Lambda", "d) Glacier"],
            "answer": "b"
        },
        {
            "question": "Quel service permet de gérer le DNS sur AWS ?",
            "options": ["a) CloudTrail", "b) Route 53", "c) CloudFront", "d) S3"],
            "answer": "b"
        },
        {
            "question": "Quel service est utilisé pour la diffusion de contenu ?",
            "options": ["a) EC2", "b) S3", "c) CloudFront", "d) RDS"],
            "answer": "c"
        }
    ],
    "kubernetes": [
        {
            "question": "Quel est le but principal de Kubernetes ?",
            "options": ["a) Hébergement web", "b) Orchestration de conteneurs", "c) Gestion de base de données", "d) Stockage de fichiers"],
            "answer": "b"
        },
        {
            "question": "Quel composant de Kubernetes gère l'état du cluster ?",
            "options": ["a) kubelet", "b) kube-proxy", "c) etcd", "d) kubectl"],
            "answer": "c"
        },
        {
            "question": "Qu'est-ce qu'un Pod dans Kubernetes ?",
            "options": ["a) Un seul conteneur", "b) Un groupe de conteneurs", "c) Un nœud du cluster", "d) Un service"],
            "answer": "b"
        },
        {
            "question": "Quelle commande applique une configuration dans Kubernetes ?",
            "options": ["a) kubectl create", "b) kubectl apply", "c) kubectl deploy", "d) kubectl update"],
            "answer": "b"
        },
        {
            "question": "Qu'est-ce qu'un Service dans Kubernetes ?",
            "options": ["a) Un type de Pod", "b) Un moyen d'exposer des Pods", "c) Une solution de stockage", "d) Un protocole réseau"],
            "answer": "b"
        },
        {
            "question": "Quelle ressource Kubernetes définit comment exécuter un conteneur ?",
            "options": ["a) Deployment", "b) ReplicaSet", "c) StatefulSet", "d) Job"],
            "answer": "a"
        }
    ]
}
FRENCH_OPEN_QUESTIONS = {
    "python": [
        {
            "question": "Qu'est-ce qu'une liste en compréhension en Python ?",
            "answer": "Une liste en compréhension est une construction syntaxique qui permet de créer des listes de manière concise en appliquant une expression à chaque élément d'un itérable, éventuellement avec une condition."
        },
        {
            "question": "Expliquez la différence entre '==' et 'is' en Python.",
            "answer": "'==' compare les valeurs des objets, tandis que 'is' vérifie s'ils référencent le même objet en mémoire (identité)."
        },
        {
            "question": "Qu'est-ce qu'un décorateur en Python ?",
            "answer": "Un décorateur est une fonction qui prend une autre fonction en entrée et retourne une fonction modifiée. Il est souvent utilisé pour ajouter des comportements sans modifier le code original."
        }
    ],
    "html": [
        {
            "question": "Quelle est la structure de base d'un document HTML ?",
            "answer": "La structure de base comprend une déclaration <!DOCTYPE html>, suivie de <html>, un <head> avec des métadonnées et un <body> contenant le contenu visible."
        },
        {
            "question": "Quel est le but de la balise <meta> ?",
            "answer": "La balise <meta> fournit des métadonnées sur le document HTML, comme l'encodage, l'auteur ou des instructions pour les moteurs de recherche."
        }
    ],
    "css": [
        {
            "question": "Quelle est la différence entre une classe et un ID en CSS ?",
            "answer": "Une classe est préfixée par un point (.) et peut être utilisée sur plusieurs éléments. Un ID est préfixé par un dièse (#) et doit être unique dans la page."
        },
        {
            "question": "Qu'est-ce que le modèle de boîte en CSS ?",
            "answer": "Le modèle de boîte est un concept qui décrit comment les éléments HTML sont représentés : avec contenu, marge intérieure (padding), bordure et marge extérieure (margin)."
        }
    ],
    "javascript": [
        {
            "question": "Quelle est la différence entre 'let', 'var' et 'const' ?",
            "answer": "'var' a une portée de fonction, tandis que 'let' et 'const' ont une portée de bloc. 'const' empêche la réaffectation."
        },
        {
            "question": "Qu'est-ce qu'une Promise en JavaScript ?",
            "answer": "Une Promise est un objet représentant l'aboutissement ou l'échec éventuel d'une opération asynchrone, avec des méthodes .then() et .catch()."
        }
    ],
    "sql": [
        {
            "question": "Quelle est la différence entre INNER JOIN et LEFT JOIN ?",
            "answer": "INNER JOIN ne retourne que les lignes avec correspondance dans les deux tables. LEFT JOIN retourne toutes les lignes de la table de gauche même sans correspondance."
        },
        {
            "question": "Qu'est-ce qu'une clé primaire en SQL ?",
            "answer": "Une clé primaire est un identifiant unique pour chaque enregistrement dans une table. Elle ne peut pas contenir de doublons ou de valeurs NULL."
        }
    ],
    "linux": [
        {
            "question": "Quelle est la différence entre 'chmod' et 'chown' ?",
            "answer": "'chmod' change les permissions d'un fichier ou répertoire, tandis que 'chown' change le propriétaire ou le groupe."
        },
        {
            "question": "À quoi sert la commande 'grep' ?",
            "answer": "'grep' recherche des chaînes de caractères dans un fichier ou un flux de texte en utilisant des expressions régulières."
        }
    ],
    "networking": [
        {
            "question": "Qu'est-ce qu'une adresse IP ?",
            "answer": "Une adresse IP est un identifiant unique attribué à chaque appareil sur un réseau, utilisé pour l'identification et la communication."
        },
        {
            "question": "Quelle est la différence entre TCP et UDP ?",
            "answer": "TCP est orienté connexion et garantit la livraison, tandis qu'UDP est plus rapide mais ne garantit ni la livraison ni l'ordre."
        }
    ],
    "git": [
        {
            "question": "Quelle est la différence entre 'git pull' et 'git fetch' ?",
            "answer": "'git fetch' récupère les données du dépôt distant sans fusionner, alors que 'git pull' récupère et fusionne automatiquement."
        },
        {
            "question": "Que fait la commande 'git branch' ?",
            "answer": "'git branch' permet de créer, lister ou supprimer des branches dans un dépôt Git."
        }
    ],
    "docker": [
        {
            "question": "Qu'est-ce qu'une image Docker ?",
            "answer": "Une image Docker est un modèle immuable qui contient tout ce qui est nécessaire pour exécuter une application : code, dépendances et système de fichiers."
        },
        {
            "question": "Quelle est la différence entre une image Docker et un conteneur ?",
            "answer": "Une image est une définition statique, tandis qu'un conteneur est une instance en cours d'exécution de cette image."
        }
    ],
    "aws": [
        {
            "question": "Qu'est-ce qu'Amazon S3 ?",
            "answer": "Amazon S3 (Simple Storage Service) est un service de stockage d'objets sécurisé et évolutif utilisé pour héberger des fichiers ou des sauvegardes."
        },
        {
            "question": "Que fait AWS Lambda ?",
            "answer": "AWS Lambda permet d'exécuter du code sans provisionner de serveurs. C'est un service de calcul serverless basé sur des événements."
        }
    ]
}