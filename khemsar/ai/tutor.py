"""Scientific QSAR/SAR AI Tutor curriculum, self-assessment quiz, and active-study interpreter."""

from __future__ import annotations

from typing import Any

from khemsar.ai.providers import generate_llm_response
from khemsar.core.config import AISettings

LESSONS: dict[str, list[dict[str, Any]]] = {
    "es": [
        {
            "id": "L1",
            "title": "1. ¿Qué son SAR y QSAR y para qué sirven?",
            "summary": "Diferencia conceptual entre relación estructura-actividad cualitativa (SAR) y cuantitativa (QSAR), desde Hansch y Free-Wilson hasta el aprendizaje automático.",
            "key_points": [
                "SAR (Structure-Activity Relationship) identifica qué fragmentos, grupos funcionales o sustituyentes hacen que una molécula sea activa o pierda potencia al modificarse.",
                "QSAR (Quantitative SAR) construye un modelo matemático y = f(X) que relaciona descriptores fisicoquímicos y estructurales (X) con una respuesta biológica cuantitativa (y = pIC50, pKi, pEC50).",
                "¿Para qué sirven? Para priorizar síntesis orgánica, detectar qué región molecular optimizar, descartar compuestos inactivos antes de ensayos costosos y guiar reemplazos bioisostéricos.",
                "Regla de oro: Un QSAR no reemplaza el criterio químico ni el ensayo experimental; es una hipótesis cuantitativa acotada a su Dominio de Aplicabilidad."
            ],
            "formula": "pIC50 = -log10(IC50 [M])   |   Ejemplo: IC50 = 10 nM = 1e-8 M  ->  pIC50 = 8.0"
        },
        {
            "id": "L2",
            "title": "2. Curación Química y Calidad Biológica (Protocolo Fourches)",
            "summary": "Por qué 'basura que entra = basura que sale' en quimioinformática y cómo evitar mezclar ensayos incompatibles.",
            "key_points": [
                "Nunca mezcles IC50, Ki, Kd ni % de inhibición en un mismo modelo de regresión: miden fenómenos cinéticos y termodinámicos distintos.",
                "Desalado y neutralización: un contraión [Na+] o Cl- no debe cambiar la representación del farmacóforo; los tautómeros deben canonicalizarse.",
                "Duplicados: si un mismo compuesto medido en dos fuentes difiere por más de 0.5 unidades logarítmicas (factor >3x en IC50), revisa condiciones del ensayo antes de promediar.",
                "Valores censurados (> 50 uM): no son mediciones exactas para regresión, pero sí son válidos para clasificación binaria (inactivo)."
            ],
            "formula": "Delta pAct <= 0.5 log  =>  Mediana aceptable;   Delta pAct > 0.5 log  =>  Discordancia experimental"
        },
        {
            "id": "L3",
            "title": "3. Descriptores Moleculares, Fingerprints y Espacio Químico",
            "summary": "Cómo traducimos una estructura química 2D/3D en variables interpretables por la estadística y la IA.",
            "key_points": [
                "Descriptores fisicoquímicos globales (MolWt, MolLogP, TPSA, HBD, HBA, Fsp3, QED) reflejan propiedades globales de permeabilidad, solubilidad e interacciones polares.",
                "Fingerprints circulares (Morgan/ECFP4) codifican vecindarios atómicos locales: capturan subestructuras específicas clave para el reconocimiento en el sitio activo.",
                "Un enfoque híbrido (fisicoquímico + ECFP4) equilibra poder predictivo e interpretabilidad químico-medicinal."
            ],
            "formula": "Similitud de Tanimoto: T(A,B) = |A ∩ B| / |A ∪ B|   (0 = sin fragmentos comunes, 1 = idénticos)"
        },
        {
            "id": "L4",
            "title": "4. Cómo Interpretar Métricas QSAR y los 5 Principios de la OCDE",
            "summary": "Lectura científica de Q2, R2ext, Golbraikh-Tropsha, Y-scrambling y Williams Plot para saber si tu modelo es publicable.",
            "key_points": [
                "Principios OCDE: (1) Endpoint definido, (2) Algoritmo explícito, (3) Dominio de Aplicabilidad definido, (4) Bondad de ajuste, robustez y predictividad externa, (5) Interpretación mecanística.",
                "Sobreajuste vs. Predictividad real: si R2_train = 0.98 pero Q2_CV = 0.35 o R2_ext = 0.30, el modelo memorizó ruido. Un modelo paper-ready suele requerir Q2_CV > 0.5, R2_ext > 0.6 y criterios de Golbraikh-Tropsha.",
                "Y-Scrambling (cRp2 > 0.5): al permutar al azar las actividades, el modelo debe colapsar; si sigue dando R2 alto, hay correlación espuria.",
                "Williams Plot: eje X = Leverage h (lejanía estructural; límite h* = 3p/n), eje Y = residuo estandarizado (±3σ). Si una molécula nueva tiene h > h*, su predicción es extrapolación riesgosa."
            ],
            "formula": "h* = 3p / n_train   |   Outlier de actividad: |Residuo est.| > 3σ   |   Outlier estructural: h > h*"
        },
        {
            "id": "L5",
            "title": "5. Interpretación SAR: Activity Cliffs, MMP, SHAP y Bioisosterismo",
            "summary": "Pasar de predecir números a diseñar nuevas moléculas optimizadas listas para Docking y Dinámica Molecular.",
            "key_points": [
                "Activity Cliff (SALI alto): par de moléculas muy similares (Tanimoto >= 0.65) con un salto drástico de potencia (Delta pAct >= 1.0). Revelan interacciones críticas de unión (puentes de H, choques estéricos).",
                "Matched Molecular Pairs (MMP): cuantifica el efecto promedio de cambiar un grupo R1 por R2 manteniendo intacto el resto de la molécula.",
                "SHAP y Mapas Atómicos: muestran en verde qué átomos/descriptores impulsan la actividad y en magenta cuáles la penalizan.",
                "Bioisosterismo: sustituye grupos lábiles o tóxicos (ej. COOH -> tetrazol; amida -> triazol; fenilo -> biciclo[1.1.1]pentano) manteniendo reconocimiento molecular y mejorando ADME."
            ],
            "formula": "SALI(i,j) = |pAct_i - pAct_j| / (1 - Tanimoto(i,j))"
        },
    ],
    "en": [
        {
            "id": "L1",
            "title": "1. What SAR and QSAR Do & Why They Matter",
            "summary": "Core distinction between qualitative SAR and quantitative QSAR, from Hansch/Free-Wilson to modern ML.",
            "key_points": [
                "SAR identifies which chemical scaffolds, substituents, or pharmacophoric groups drive or abolish biological potency.",
                "QSAR builds a mathematical model y = f(X) linking molecular descriptors (X) to quantitative bioactivity (y = pIC50, pKi, pEC50).",
                "Purpose: prioritize synthesis, spot optimization vectors, filter inactive compounds early, and guide bioisosteric replacements.",
                "Golden rule: QSAR is a quantitative hypothesis bounded by its Applicability Domain, never a blind substitute for experiment."
            ],
            "formula": "pIC50 = -log10(IC50 [M])   |   Example: IC50 = 10 nM = 1e-8 M  ->  pIC50 = 8.0"
        },
        {
            "id": "L2",
            "title": "2. Chemical Curation & Assay Integrity (Fourches Protocol)",
            "summary": "Why data hygiene prevents mixing incompatible assays and noisy labels.",
            "key_points": [
                "Never mix IC50, Ki, Kd, and % inhibition in a single regression QSAR model.",
                "Strip counterions/salts, neutralize charges, and canonicalize tautomers prior to descriptor calculation.",
                "Duplicates differing by > 0.5 log units indicate assay discrepancy and must be flagged or excluded.",
                "Censored values (> 50 uM) are unsuitable for regression but informative for binary classification."
            ],
            "formula": "Delta pAct <= 0.5 log => Keep median;   Delta pAct > 0.5 log => Discordant replicates"
        },
        {
            "id": "L3",
            "title": "3. Descriptors, Fingerprints & Chemical Space",
            "summary": "Encoding molecular structures into interpretable physical and topological features.",
            "key_points": [
                "2D physicochemical descriptors (MolWt, LogP, TPSA, HBD, HBA, Fsp3, QED) capture global ADME and binding properties.",
                "Circular fingerprints (Morgan/ECFP4) encode atom-centered neighborhoods critical for pocket recognition.",
                "Hybrid representations combine interpretability with local substructural sensitivity."
            ],
            "formula": "Tanimoto Similarity: T(A,B) = |A ∩ B| / |A ∪ B|"
        },
        {
            "id": "L4",
            "title": "4. Interpreting QSAR Metrics & the 5 OECD Principles",
            "summary": "How to evaluate Q2, R2ext, Golbraikh-Tropsha criteria, Y-scrambling, and the Williams Plot.",
            "key_points": [
                "OECD Principles: defined endpoint, unambiguous algorithm, defined Applicability Domain, goodness-of-fit/robustness/predictivity, and mechanistic interpretation.",
                "Overfitting trap: R2_train = 0.98 with Q2_CV = 0.35 indicates memorization. Paper-ready models generally require Q2_CV > 0.5, R2_ext > 0.6, and Golbraikh-Tropsha compliance.",
                "Y-Scrambling (cRp2 > 0.5): permuting Y must destroy model performance; otherwise chance correlation is present.",
                "Williams Plot: X = leverage h (warning threshold h* = 3p/n), Y = standardized residual (±3σ). Compounds with h > h* are structural extrapolations."
            ],
            "formula": "h* = 3p / n_train   |   Response outlier: |Std. Residual| > 3σ   |   Structural outlier: h > h*"
        },
        {
            "id": "L5",
            "title": "5. SAR Interpretation: Activity Cliffs, MMP, SHAP & Bioisosterism",
            "summary": "Translating statistical patterns into actionable medicinal chemistry hypotheses for Docking & MD.",
            "key_points": [
                "Activity Cliffs (high SALI): structurally close pairs with sharp potency jumps reveal key binding hotspots.",
                "Matched Molecular Pairs (MMP) quantify average potency shifts for specific functional group swaps.",
                "SHAP & atomic attribution maps highlight favorable (green) vs. detrimental (magenta) substructures.",
                "Bioisosteric design replaces metabolically/synthetically problematic motifs while preserving pharmacophoric interactions."
            ],
            "formula": "SALI(i,j) = |pAct_i - pAct_j| / (1 - Tanimoto(i,j))"
        },
    ],
    "pt": [
        {
            "id": "L1",
            "title": "1. O que são SAR e QSAR e para que servem?",
            "summary": "Diferença entre relação estrutura-atividade qualitativa (SAR) e quantitativa (QSAR), de Hansch ao aprendizado de máquina.",
            "key_points": [
                "SAR identifica quais fragmentos ou substituintes aumentam ou eliminam a atividade biológica.",
                "QSAR constrói um modelo matemático y = f(X) relacionando descritores moleculares (X) à potência biológica (y = pIC50, pKi).",
                "Serve para priorizar síntese, identificar vetores de otimização e guiar substituições bioisostéricas.",
                "Regra fundamental: todo QSAR é válido apenas dentro de seu Domínio de Aplicabilidade."
            ],
            "formula": "pIC50 = -log10(IC50 [M])   |   Exemplo: IC50 = 10 nM = 1e-8 M  ->  pIC50 = 8.0"
        },
        {
            "id": "L2",
            "title": "2. Curadoria Química e Qualidade dos Ensaios (Protocolo Fourches)",
            "summary": "Por que a higiene dos dados evita misturar ensaios incompatíveis e artefatos estatísticos.",
            "key_points": [
                "Nunca misture IC50, Ki, Kd e % de inibição no mesmo modelo QSAR de regressão.",
                "Remova sais, neutralize cargas e padronize tautômeros antes de calcular descritores.",
                "Duplicatas com diferença > 0.5 unidades log indicam discordância experimental.",
                "Dados censurados (> 50 uM) devem ser excluídos da regressão ou usados apenas em classificação binária."
            ],
            "formula": "Delta pAct <= 0.5 log => Mediana aceita;   Delta pAct > 0.5 log => Replicatas discordantes"
        },
        {
            "id": "L3",
            "title": "3. Descritores Moleculares, Fingerprints e Espaço Químico",
            "summary": "Conversão de estruturas químicas em variáveis físico-químicas e topológicas interpretáveis.",
            "key_points": [
                "Descritores físico-químicos (MolWt, LogP, TPSA, HBD, HBA, Fsp3, QED) representam propriedades globais.",
                "Fingerprints circulares (Morgan/ECFP4) capturam vizinhanças atômicas locais essenciais ao sítio ativo.",
                "Modelos híbridos combinam interpretabilidade medicinal com alta capacidade preditiva."
            ],
            "formula": "Similaridade de Tanimoto: T(A,B) = |A ∩ B| / |A ∪ B|"
        },
        {
            "id": "L4",
            "title": "4. Interpretação de Métricas QSAR e os 5 Princípios da OCDE",
            "summary": "Como interpretar Q2, R2ext, Golbraikh-Tropsha, Y-scrambling e o Gráfico de Williams.",
            "key_points": [
                "Os 5 Princípios da OCDE exigem endpoint definido, algoritmo explícito, Domínio de Aplicabilidade, validação interna/externa e interpretação mecanística.",
                "Sobreajuste: R2_train alto com Q2_CV baixo indica memorização. Modelos publicáveis requerem Q2_CV > 0.5 e R2_ext > 0.6.",
                "Y-Scrambling (cRp2 > 0.5) comprova ausência de correlação ao acaso.",
                "Gráfico de Williams: leverage h > h* (= 3p/n) indica extrapolação estrutural; |resíduo| > 3σ indica outlier de resposta."
            ],
            "formula": "h* = 3p / n_train   |   Outlier de resposta: |Resíduo| > 3σ   |   Outlier estrutural: h > h*"
        },
        {
            "id": "L5",
            "title": "5. Interpretação SAR: Activity Cliffs, MMP, SHAP e Bioisosterismo",
            "summary": "Transformando análises estatísticas em hipóteses de química medicinal para Docking e Dinâmica Molecular.",
            "key_points": [
                "Activity Cliffs (SALI elevado) revelam interações críticas no sítio de ligação.",
                "Matched Molecular Pairs (MMP) quantificam o ganho ou perda média de potência de cada troca química.",
                "SHAP e mapas atômicos mostram subestruturas favoráveis (verde) e desfavoráveis (magenta).",
                "Bioisosterismo otimiza potência e ADME antes de gerar confôrmeros 3D para docking e dinâmica molecular."
            ],
            "formula": "SALI(i,j) = |pAct_i - pAct_j| / (1 - Tanimoto(i,j))"
        },
    ],
}

QUIZZES: dict[str, list[dict[str, Any]]] = {
    "es": [
        {
            "question": "Si tu modelo QSAR obtiene R2_train = 0.97, pero Q2_CV = 0.28 y R2_ext = 0.22, ¿qué ocurrió?",
            "options": [
                "El modelo está listo para publicar porque R2_train es casi 1.0.",
                "Hay sobreajuste (overfitting) severo: memorizó el entrenamiento pero no generaliza.",
                "Se deben mezclar datos de Ki e IC50 para mejorar R2_ext."
            ],
            "answer_index": 1,
            "explanation": "Un R2_train alto acompañado de Q2_CV y R2_ext bajos demuestra memorización de ruido. Nunca debe validarse un QSAR solo con R2_train."
        },
        {
            "question": "En el Williams Plot, una molécula de prueba tiene Leverage h = 0.92 (con h* = 0.45) y residuo estandarizado = 0.4. ¿Cómo se interpreta?",
            "options": [
                "Está fuera del Dominio de Aplicabilidad estructural (extrapolación riesgosa aunque su residuo haya sido bajo por casualidad).",
                "Es un Activity Cliff confirmado.",
                "Significa que el ensayo biológico fue erróneo."
            ],
            "answer_index": 0,
            "explanation": "Cuando h > h*, el compuesto es estructuralmente distante del conjunto de entrenamiento (alta palanca) y su predicción debe considerarse extrapolación fuera del AD."
        },
        {
            "question": "¿Para qué sirve el Y-Scrambling (cRp2 > 0.5)?",
            "options": [
                "Para generar moléculas de novo.",
                "Para verificar que el modelo no obtuvo buen desempeño por correlación espuria al azar.",
                "Para convertir IC50 en pIC50."
            ],
            "answer_index": 1,
            "explanation": "Al permutar aleatoriamente la variable Y, cualquier modelo válido debe perder capacidad predictiva; un cRp2 > 0.5 respalda que la relación QSAR no es casual."
        },
    ],
    "en": [
        {
            "question": "Your QSAR model achieves R2_train = 0.97, but Q2_CV = 0.28 and R2_ext = 0.22. What happened?",
            "options": [
                "The model is paper-ready because R2_train is near 1.0.",
                "Severe overfitting: the model memorized training noise and fails to generalize.",
                "You should mix Ki and IC50 assays to raise R2_ext."
            ],
            "answer_index": 1,
            "explanation": "High training R2 combined with poor Q2_CV and R2_ext is the hallmark of overfitting."
        },
        {
            "question": "In a Williams Plot, a test compound has leverage h = 0.92 (h* = 0.45) and standardized residual = 0.4. How do you interpret it?",
            "options": [
                "It lies outside the structural Applicability Domain (risky extrapolation).",
                "It proves the biological assay failed.",
                "It is a confirmed Activity Cliff."
            ],
            "answer_index": 0,
            "explanation": "Leverage h > h* means the compound is structurally distant from training molecules, making predictions extrapolative."
        },
        {
            "question": "Why is Y-scrambling (cRp2 > 0.5) required in rigorous QSAR studies?",
            "options": [
                "To generate 3D conformers.",
                "To rule out chance correlation between descriptors and activity.",
                "To neutralize molecular salts."
            ],
            "answer_index": 1,
            "explanation": "Randomizing Y breaks true structure-activity links; cRp2 > 0.5 confirms the real model strongly outperforms chance."
        },
    ],
    "pt": [
        {
            "question": "Se um modelo QSAR apresenta R2_train = 0.97, mas Q2_CV = 0.28 e R2_ext = 0.22, o que ocorreu?",
            "options": [
                "O modelo está pronto para publicação.",
                "Há sobreajuste (overfitting) severo: memorizou o treino sem generalizar.",
                "Deve-se misturar Ki e IC50 no mesmo modelo."
            ],
            "answer_index": 1,
            "explanation": "R2 de treinamento alto com Q2_CV e R2_ext baixos indica memorização e falta de poder preditivo."
        },
        {
            "question": "No gráfico de Williams, uma molécula possui leverage h = 0.92 (h* = 0.45). Como interpretar?",
            "options": [
                "Está fora do Domínio de Aplicabilidade estrutural (extrapolação).",
                "O ensaio biológico está errado.",
                "É um bioisóstero perfeito."
            ],
            "answer_index": 0,
            "explanation": "Quando h > h*, o composto está distante do espaço químico de treinamento."
        },
        {
            "question": "Qual a função do Y-Scrambling (cRp2 > 0.5)?",
            "options": [
                "Gerar confôrmeros 3D.",
                "Descartar correlação espúria ao acaso.",
                "Converter IC50 em pIC50."
            ],
            "answer_index": 1,
            "explanation": "Permutar Y testa se o desempenho real supera modelos gerados por acaso."
        },
    ],
}


def deterministic_study_interpretation(study_context: dict[str, Any], lang: str = "es") -> str:
    """Produce a rigorous scientific interpretation directly from current study metrics."""
    qsar = study_context.get("qsar") or {}
    sar = study_context.get("sar") or {}
    curation = study_context.get("curation") or {}
    denovo = study_context.get("denovo") or {}

    lines: list[str] = []
    if not qsar and not curation:
        if lang == "en":
            return "No active study metrics loaded yet. Load the Demo Study or run a ChEMBL/PubChem query in the QSAR/SAR Studio, then click 'Interpret my active study' to receive a tailored scientific analysis."
        if lang == "pt":
            return "Ainda não há métricas de estudo ativas. Carregue o Estudo Demo ou execute uma busca no Estúdio QSAR/SAR e clique novamente para receber a interpretação científica detalhada."
        return "Aún no hay un estudio activo cargado. Carga el Estudio Demo (COX-2) o realiza una búsqueda en el Estudio QSAR/SAR, y luego vuelve a pulsar este botón para analizar científicamente tus métricas reales."

    rep = curation.get("report", {})
    if rep:
        if lang == "en":
            lines.append(f"**1. Data Curation:** {rep.get('raw_count', 0)} raw records -> **{rep.get('final_count', 0)} curated unique molecules** ({curation.get('endpoint_used', 'IC50')}). Excluded {rep.get('excluded_discordant_duplicates', 0)} discordant duplicates and {rep.get('excluded_invalid_or_inorganic_or_mixture', 0)} invalid/inorganic entries.")
        elif lang == "pt":
            lines.append(f"**1. Curadoria:** {rep.get('raw_count', 0)} registros brutos -> **{rep.get('final_count', 0)} moléculas curadas** ({curation.get('endpoint_used', 'IC50')}).")
        else:
            lines.append(f"**1. Curadoria Química:** De {rep.get('raw_count', 0)} registros iniciales quedaron **{rep.get('final_count', 0)} moléculas únicas curadas** ({curation.get('endpoint_used', 'IC50')}); se descartaron {rep.get('excluded_discordant_duplicates', 0)} duplicados discordantes y {rep.get('excluded_invalid_or_inorganic_or_mixture', 0)} estructuras inválidas/inorgánicas/mezclas.")

    if qsar:
        m = qsar.get("best_metrics", {})
        ys = qsar.get("y_scrambling", {})
        ad = qsar.get("applicability_domain", {})
        algo = qsar.get("best_algorithm", "")
        split_m = qsar.get("split_method_used", "")
        if qsar.get("task_type") == "regression":
            q2 = m.get("Q2_CV", 0.0)
            r2ext = m.get("R2_ext", 0.0)
            gt = m.get("Golbraikh_Tropsha_pass", False)
            crp2 = ys.get("cRp2", 0.0)
            cov = ad.get("test_coverage_pct", 0.0)
            verdict = "SÓLIDO / PAPER-READY" if (q2 >= 0.5 and r2ext >= 0.5 and crp2 >= 0.45) else "PRELIMINAR (revisar tamaño muestral o partición)"
            if lang == "en":
                lines.append(f"**2. QSAR Performance ({algo}, {split_m} split):** Q2_CV = {q2}, R2_ext = {r2ext}, RMSE_ext = {m.get('RMSE_ext')}, CCC_ext = {m.get('CCC_ext')}, Golbraikh-Tropsha = {'PASS' if gt else 'CHECK'}.")
                lines.append(f"**3. Robustness & AD:** Y-scrambling cRp2 = {crp2}; External test AD coverage = {cov}% (h* = {ad.get('h_star')}).")
            elif lang == "pt":
                lines.append(f"**2. Desempenho QSAR ({algo}, split {split_m}):** Q2_CV = {q2}, R2_ext = {r2ext}, RMSE_ext = {m.get('RMSE_ext')}, Golbraikh-Tropsha = {'APROVADO' if gt else 'REVISAR'}.")
                lines.append(f"**3. Robustez e DA:** cRp2 = {crp2}; Cobertura no Domínio de Aplicabilidade = {cov}% (h* = {ad.get('h_star')}).")
            else:
                lines.append(f"**2. Desempeño QSAR ({algo}, partición `{split_m}` — estado {verdict}):** $Q^2_{{\\text{{CV}}}} = {q2}$, $R^2_{{\\text{{ext}}}} = {r2ext}$, $\\text{{RMSE}}_{{\\text{{ext}}}} = {m.get('RMSE_ext')}$, $\\text{{CCC}}_{{\\text{{ext}}}} = {m.get('CCC_ext')}$, criterios Golbraikh–Tropsha: {'APROBADO' if gt else 'REVISAR'}.")
                lines.append(f"**3. Robustez y Dominio de Aplicabilidad:** Y-scrambling $cR_p^2 = {crp2}$ ({'sin correlación espuria' if ys.get('passes_chance_correlation_check') else 'precaución por tamaño/correlación'}); cobertura AD externa = {cov}% ($h^* = {ad.get('h_star')}$, {ad.get('n_test_outliers', 0)} outliers).")
        else:
            lines.append(f"**2. Classification QSAR ({algo}):** MCC_CV = {m.get('MCC_CV')}, MCC_ext = {m.get('MCC_ext')}, ROC_AUC_ext = {m.get('ROC_AUC_ext')}, Balanced Accuracy = {m.get('Balanced_Accuracy_ext')}.")

    if sar:
        n_cliffs = sar.get("activity_cliffs", {}).get("n_cliffs_found", 0)
        n_mmp = sar.get("mmp", {}).get("n_unique_transforms", 0)
        top_feats = [f["feature"] for f in (sar.get("shap", {}).get("top_features") or [])[:4]]
        if lang == "en":
            lines.append(f"**4. SAR & Interpretability:** Detected {n_cliffs} Activity Cliffs (SALI) and {n_mmp} MMP transforms. Top SHAP drivers: {', '.join(top_feats) or 'N/A'}.")
        elif lang == "pt":
            lines.append(f"**4. SAR & Interpretabilidade:** {n_cliffs} Activity Cliffs e {n_mmp} transformações MMP. Principais variáveis SHAP: {', '.join(top_feats) or 'N/A'}.")
        else:
            lines.append(f"**4. SAR e Interpretabilidad:** Se detectaron **{n_cliffs} Activity Cliffs** (SALI) y **{n_mmp} transformaciones MMP**. Descriptores líderes según SHAP: {', '.join(top_feats) or 'N/A'}.")

    if denovo and denovo.get("candidates"):
        top_c = denovo["candidates"][0]
        in_ad_n = sum(1 for c in denovo["candidates"] if c.get("in_ad"))
        if lang == "en":
            lines.append(f"**5. De Novo Candidates:** Generated {len(denovo['candidates'])} molecules ({in_ad_n} inside AD). Top MPO candidate: {top_c['candidate_id']} ({top_c['bioisostere_rule']}, MPO={top_c['MPO_score']}, SA={top_c['SA_Score']}).")
        elif lang == "pt":
            lines.append(f"**5. Candidatos De Novo:** {len(denovo['candidates'])} gerados ({in_ad_n} no DA). Melhor candidato: {top_c['candidate_id']} ({top_c['bioisostere_rule']}, MPO={top_c['MPO_score']}).")
        else:
            lines.append(f"**5. Generación De Novo y Bioisósteros:** Se generaron {len(denovo['candidates'])} candidatos ({in_ad_n} dentro del Dominio de Aplicabilidad). Mejor candidato MPO: `{top_c['candidate_id']}` vía `{top_c['bioisostere_rule']}` (MPO={top_c['MPO_score']}, QED={top_c['QED']}, SA={top_c['SA_Score']}).")

    return "\n\n".join(lines)


async def answer_tutor_question(
    question: str,
    lang: str,
    ai_settings: AISettings,
    study_context: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Answer any QSAR/SAR pedagogical or interpretation question via LLM or rigorous offline knowledge."""
    ctx_summary = deterministic_study_interpretation(study_context or {}, lang=lang)
    lang_label = {"es": "Spanish", "en": "English", "pt": "Portuguese"}.get(lang, "Spanish")

    sys_prompt = (
        f"You are KhemSAR AI Tutor, a PhD-level medicinal chemist and cheminformatician. "
        f"Respond in {lang_label} with scientific rigor, clarity, and didactic examples. "
        f"Always explain what QSAR and SAR do, statistical pitfalls (overfitting, assay mixing, applicability domain, Y-scrambling), "
        f"and how to interpret results for peer-reviewed publications. Never invent metrics not present in the context."
    )
    user_prompt = f"Active study summary:\n{ctx_summary}\n\nStudent/Researcher question:\n{question}"

    llm_ans, used_provider = await generate_llm_response(sys_prompt, user_prompt, ai_settings)
    if llm_ans:
        return {"answer": llm_ans, "provider": used_provider}

    # Rich deterministic offline pedagogical response
    ql = question.lower()
    if any(k in ql for k in ("mi estudio", "my study", "meu estudo", "interpreta", "interpret", "analiza")):
        ans = ctx_summary
    elif any(k in ql for k in ("williams", "aplicabilidad", "applicability", "leverage", "h*")):
        ans = {
            "es": "El **Williams Plot** evalúa el **Dominio de Aplicabilidad (Principio 3 de la OCDE)**:\n- **Eje X (Leverage $h$)**: mide qué tan lejos estructuralmente está una molécula del centro del conjunto de entrenamiento. El umbral de alerta es $h^* = 3p/n$. Si $h > h^*$, el modelo está extrapolando.\n- **Eje Y (Residuo estandarizado)**: mide el error de predicción en desviaciones estándar ($\\pm 3\\sigma$). Valores fuera de $[-3, +3]$ indican *outliers* de actividad (posibles errores experimentales o *activity cliffs*).\n- **Regla de oro**: Solo confía plenamente en predicciones *de novo* que caigan dentro de $h \\le h^*$ y tengan buena similitud de Tanimoto al entrenamiento.",
            "en": "The **Williams Plot** checks the **Applicability Domain (OECD Principle 3)**:\n- **X-axis (Leverage h)** measures structural distance from the training set; threshold h* = 3p/n. Compounds with h > h* are extrapolations.\n- **Y-axis (Standardized Residual)** detects response outliers outside ±3σ.\n- For de novo design, prioritize candidates inside h <= h* with strong k-NN Tanimoto similarity.",
            "pt": "O **Gráfico de Williams** avalia o **Domínio de Aplicabilidade (Princípio 3 da OCDE)**: leverage h > h* (= 3p/n) indica extrapolação estrutural e |resíduo| > 3σ indica outlier de resposta."
        }.get(lang, ctx_summary)
    elif any(k in ql for k in ("q2", "r2", "overfit", "sobreaj", "scrambl", "golbraikh")):
        ans = {
            "es": "Para evaluar si un QSAR es **paper-ready** no basta un $R^2_{\\text{train}}$ alto:\n1. **$Q^2_{\\text{CV}} > 0.5$**: mide estabilidad interna por validación cruzada.\n2. **$R^2_{\\text{ext}} > 0.6$ y criterios de Golbraikh–Tropsha** ($0.85 \\le k, k' \\le 1.15$, $R_0^2$ cercano a $R^2$): garantizan predictividad real sobre moléculas nunca vistas.\n3. **Y-Scrambling ($cR_p^2 > 0.5$)**: confirma que el modelo no aprendió correlaciones aleatorias.",
            "en": "A paper-ready QSAR requires more than training R2: look for Q2_CV > 0.5, external R2_ext > 0.6, Golbraikh-Tropsha slope compliance (0.85 <= k <= 1.15), and Y-scrambling cRp2 > 0.5 to exclude chance correlation.",
            "pt": "Um QSAR publicável exige Q2_CV > 0.5, R2_ext > 0.6, critérios de Golbraikh-Tropsha e cRp2 > 0.5 no Y-scrambling."
        }.get(lang, ctx_summary)
    elif any(k in ql for k in ("cliff", "sali", "mmp", "bioisoster", "shap")):
        ans = {
            "es": "- **Activity Cliffs (SALI)**: pares casi idénticos con gran salto de potencia; señalan grupos farmacofóricos críticos.\n- **MMP (Matched Molecular Pairs)**: cuantifica el cambio promedio $\\Delta p\\text{Act}$ de sustituir un fragmento por otro.\n- **SHAP y Mapas Atómicos**: explican qué descriptores y átomos impulsan positiva o negativamente la predicción (Principio 5 OCDE).\n- **Bioisosterismo**: aplica reemplazos medicinales (ej. COOH $\\leftrightarrow$ tetrazol, fenilo $\\leftrightarrow$ BCP/piridina) para mejorar potencia y ADME antes de Docking y MD.",
            "en": "- **Activity Cliffs (SALI)**: near-identical pairs with sharp potency jumps.\n- **MMP**: average ΔpAct per structural swap.\n- **SHAP & Atomic Maps**: mechanistic attribution (OECD Principle 5).\n- **Bioisosteres**: replace problematic motifs while keeping key target interactions.",
            "pt": "- **Activity Cliffs (SALI)**: pares similares com grande salto de potência.\n- **MMP**: efeito médio ΔpAct de trocas químicas.\n- **SHAP**: atribuição mecanística (Princípio 5 OCDE).\n- **Bioisósteros**: substituições racionais antes do Docking e Dinâmica Molecular."
        }.get(lang, ctx_summary)
    else:
        ans = (
            LESSONS.get(lang, LESSONS["es"])[0]["summary"]
            + "\n\n"
            + "\n".join(f"- {kp}" for kp in LESSONS.get(lang, LESSONS["es"])[0]["key_points"])
            + f"\n\n---\n{ctx_summary}"
        )

    return {"answer": ans, "provider": "offline_scientific_engine"}
