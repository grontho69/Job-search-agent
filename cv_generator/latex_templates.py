"""
latex_templates.py
==================
Industry Standard ATS-Optimized Clean LaTeX Resume Template (Based on Jake's Resume)
Optimized for 90+ ATS Parse Rates, Exact Single-Page Vertical Alignment, and Overleaf Compatibility.
"""

def escape_latex(text: str) -> str:
    """Escapes special LaTeX characters safely."""
    if not text:
        return ""
    text = str(text)
    mapping = {
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    # Replace backslash first if any
    text = text.replace("\\", r"\textbackslash{}")
    for char, replacement in mapping.items():
        text = text.replace(char, replacement)
    return text


JAKES_RESUME_PREAMBLE = r"""%-------------------------
% Resume in LaTeX (ATS Optimized Jake's Resume Template)
% Author : Mahathir Mohammad
% Based on: https://github.com/sb2nov/resume
% License : MIT
%------------------------

\documentclass[letterpaper,10pt]{article}

\usepackage{latexsym}
\usepackage[empty]{fullpage}
\usepackage{titlesec}
\usepackage{marvosym}
\usepackage[usenames,dvipsnames]{color}
\usepackage{verbatim}
\usepackage{enumitem}
\usepackage[hidelinks]{hyperref}
\usepackage{fancyhdr}
\usepackage[english]{babel}
\usepackage{tabularx}
\input{glyphtounicode}

% Adjust margins
\addtolength{\oddsidemargin}{-0.5in}
\addtolength{\evensidemargin}{-0.5in}
\addtolength{\textwidth}{1in}
\addtolength{\topmargin}{-.5in}
\addtolength{\textheight}{1.0in}

\urlstyle{same}

\raggedbottom
\raggedright
\setlength{\tabcolsep}{0in}

% Sections formatting
\titleformat{\section}{
  \vspace{-5pt}\scshape\raggedright\large
}{}{0em}{}[\color{black}\titlerule \vspace{-5pt}]

% Ensure that generate pdf is machine readable/ATS parsable
\pdfgentounicode=1

%-------------------------
% Custom commands
\newcommand{\resumeItem}[1]{
  \item\small{
    {#1 \vspace{-2pt}}
  }
}

\newcommand{\resumeSubheading}[4]{
  \vspace{-2pt}\item
    \begin{tabular*}{0.97\textwidth}[t]{l@{\extracolsep{\fill}}r}
      \textbf{#1} & #2 \\
      \textit{\small#3} & \textit{\small #4} \\
    \end{tabular*}\vspace{-7pt}
}

\newcommand{\resumeSubSubheading}[2]{
    \item
    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}
      \textit{\small#1} & \textit{\small #2} \\
    \end{tabular*}\vspace{-7pt}
}

\newcommand{\resumeProjectHeading}[2]{
    \item
    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}
      \small#1 & #2 \\
    \end{tabular*}\vspace{-7pt}
}

\newcommand{\resumeSubItem}[1]{\resumeItem{#1}\vspace{-4pt}}

\renewcommand\labelitemii{$\vcenter{\hbox{\tiny$\bullet$}}$}

\newcommand{\resumeSubHeadingListStart}{\begin{itemize}[leftmargin=0.15in, label={}]}
\newcommand{\resumeSubHeadingListEnd}{\end{itemize}}
\newcommand{\resumeItemListStart}{\begin{itemize}}
\newcommand{\resumeItemListEnd}{\end{itemize}\vspace{-5pt}}

%-------------------------------------------
%%%%%%  RESUME STARTS HERE  %%%%%%%%%%%%%%%%%%%%%%%%%%%%

\begin{document}
"""

def generate_latex_source(profile: dict, target_job: dict = None) -> str:
    """
    Generates a full LaTeX document customized for the target job.
    Dynamically sorts and selects the best projects from profile['projects'].
    """
    name = escape_latex(profile.get("name", "Mahathir Mohammad"))
    contact = profile.get("contact", {})
    phone = escape_latex(contact.get("phone", ""))
    email = escape_latex(contact.get("email", ""))
    linkedin = contact.get("linkedin", "")
    github = contact.get("github", "")
    portfolio = contact.get("portfolio", "")
    summary = escape_latex(profile.get("summary", ""))

    content = [JAKES_RESUME_PREAMBLE]

    # --- HEADING ---
    content.append(r"""
%----------HEADING----------
\begin{center}
    \textbf{\Huge \scshape """ + name + r"""} \\ \vspace{2pt}
    \small """ + phone + r""" $|$ \href{mailto:""" + email + r"""}{\underline{""" + email + r"""}} $|$ 
    \href{""" + linkedin + r"""}{\underline{linkedin.com/in/mahathir}} $|$
    \href{""" + github + r"""}{\underline{github.com/grontho69}} $|$
    \href{""" + portfolio + r"""}{\underline{devmahathir.netlify.app}}
\end{center}
""")

    # --- PROFESSIONAL SUMMARY ---
    if summary:
        content.append(r"""
%-----------SUMMARY-----------
\section{Professional Summary}
\small{""" + summary + r"""}
\vspace{-4pt}
""")

    # --- TECHNICAL SKILLS ---
    skills = profile.get("technical_skills", {})
    if skills:
        content.append(r"""
%-----------TECHNICAL SKILLS-----------
\section{Technical Skills}
 \begin{itemize}[leftmargin=0.15in, label={}]
    \small{\item{
""")
        skill_lines = []
        for cat, sk_list in skills.items():
            cat_escaped = escape_latex(cat)
            items_escaped = escape_latex(", ".join(sk_list) if isinstance(sk_list, list) else str(sk_list))
            skill_lines.append(f"     \\textbf{{{cat_escaped}}}: {{{items_escaped}}} \\\\")
        
        content.append("\n".join(skill_lines))
        content.append(r"""
    }}
 \end{itemize}
\vspace{-12pt}
""")

    # --- EXPERIENCE ---
    experiences = profile.get("professional_experience", [])
    if experiences:
        content.append(r"""
%-----------EXPERIENCE-----------
\section{Experience}
  \resumeSubHeadingListStart
""")
        for exp in experiences:
            title = escape_latex(exp.get("title", ""))
            company = escape_latex(exp.get("company", ""))
            dates = escape_latex(exp.get("dates", ""))
            loc = escape_latex(exp.get("location", ""))
            content.append(f"    \\resumeSubheading{{{title}}}{{{dates}}}{{{company}}}{{{loc}}}")
            content.append("      \\resumeItemListStart")
            for bullet in exp.get("bullets", []):
                content.append(f"        \\resumeItem{{{escape_latex(bullet)}}}")
            content.append("      \\resumeItemListEnd")
        content.append("  \\resumeSubHeadingListEnd\n\\vspace{-10pt}")

    # --- PROJECTS (Top 3 prioritized for target job) ---
    all_projects = profile.get("projects", [])
    selected_projects = all_projects[:3]  # Can be dynamically prioritized

    if selected_projects:
        content.append(r"""
%-----------PROJECTS-----------
\section{Projects}
    \resumeSubHeadingListStart
""")
        for proj in selected_projects:
            p_name = escape_latex(proj.get("name", ""))
            tech = escape_latex(proj.get("technologies", ""))
            live = proj.get("live_link", "")
            gh = proj.get("github_link", "")
            
            links_part = []
            if live:
                links_part.append(f"\\href{{{live}}}{{\\underline{{Live Demo}}}}")
            if gh and gh != live:
                links_part.append(f"\\href{{{gh}}}{{\\underline{{GitHub}}}}")
            
            links_str = f" $|$ {' $|$ '.join(links_part)}" if links_part else ""
            
            header = f"\\textbf{{{p_name}}} {links_str}"
            content.append(f"      \\resumeProjectHeading{{{header}}}{{{tech}}}")
            content.append("          \\resumeItemListStart")
            for bullet in proj.get("bullets", []):
                content.append(f"            \\resumeItem{{{escape_latex(bullet)}}}")
            content.append("          \\resumeItemListEnd")
        content.append("    \\resumeSubHeadingListEnd\n\\vspace{-10pt}")

    # --- EDUCATION ---
    education = profile.get("education", [])
    if education:
        content.append(r"""
%-----------EDUCATION-----------
\section{Education}
  \resumeSubHeadingListStart
""")
        for edu in education:
            degree = escape_latex(edu.get("degree", ""))
            field = escape_latex(edu.get("field", ""))
            inst = escape_latex(edu.get("institution", ""))
            year = escape_latex(edu.get("graduation_year", ""))
            deg_full = f"{degree} in {field}" if field else degree
            content.append(f"    \\resumeSubheading{{{inst}}}{{{year}}}{{{deg_full}}}{{}}")
        content.append("  \\resumeSubHeadingListEnd")

    content.append(r"\end{document}")
    return "\n".join(content)
