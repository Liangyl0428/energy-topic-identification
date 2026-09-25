from refine_common import clean
import re

SIGMA=re.compile(r'Wydawnictwo\s+SIGMA[-–]NOT\s+wydaje\s+czasopisma\s+fachowe\s+informujące\s+swoich\s+czytelników\s+o\s+najnowszych\s+osiągnięciach\s+naukowych\s+i\s+nowoczesnych\s+rozwiązaniach\s+technicznych\s+w\s+Polsce\s+i\s+na\s+świecie,?\s+popularyzuje\s+problemy\s+techniczne\s+oraz\s+poszerza\s+wiedzę\s+i\s+kulturę\s+techniczną\.?',re.I)
CHEM=re.compile(r'ChemInform is a weekly Abstracting Service, delivering concise information at a glance that was extracted from about \d+ leading journals\.\s*To access a ChemInform Abstract(?: of an article which was published elsewhere)?, please (?:click on HTML or PDF|select a [“"\']Full Text[”"\'] option)\.(?:\s*The original article is trackable via the [“"\']References[”"\'] option\.)?',re.I)
CANADIAN=re.compile(r'The Canadian Journal of Chemical Engineering, published by Wiley on behalf of The Canadian Society for Chemical Engineering, is the forum for publication of high quality original research articles, new theoretical interpretation or experimental findings and critical reviews in the science or industrial practice of chemical and biochemical processes\.',re.I)
DOI=re.compile(r'(?:https?://(?:dx\.)?doi\.org/)?10\.\d{4,9}/\S+',re.I)
META=re.compile(r'^(?:Graphical Abstract\s*[:：]|Cover (?:Picture|Image|Feature|Page)\s*[:：]|(?:Front|Back|Inside Front|Inside Back) Cover\b|Issue Cover\b|Table of Contents\s*[:：]|Editorial Board\b|Author Index\b|Subject Index\b|Contents\s*[:：]|Correction to:|Retraction (?:Note|Notice):|Erratum to:)',re.I)
PREFIX=re.compile(r'^ChemInform Abstract:\s*',re.I)

def process(title,body,usable=True):
    # Source strings are never overwritten; these are derived views.
    t=clean(title);b=clean(body);flags=[]
    original_t=t;original_b=b
    if 'sigma' in b.lower():
        b,n=SIGMA.subn('',b)
        if n:flags.append('sigma_publisher_template_removed')
    if 'cheminform' in b.lower():
        b,n=CHEM.subn('',b)
        if n:flags.append('cheminform_service_template_removed')
    if 'Canadian Journal of Chemical Engineering' in b:
        b,n=CANADIAN.subn('',b)
        if n:flags.append('publisher_description_removed')
    t,n=PREFIX.subn('',t)
    if n:flags.append('cheminform_title_prefix_removed')
    b=clean(b)
    doi=bool(DOI.fullmatch(t))
    if doi:flags.append('doi_only_title')
    meta=bool(META.search(t))
    if meta:flags.append('explicit_editorial_or_correction_title')
    # Bibliographic strings and URLs alone cannot supply a semantic topic.
    title_usable=not doi and (len(re.findall(r'[^\W\d_]',t,flags=re.U))>=6 or len(re.findall(r'[\u4e00-\u9fff]',t))>=2)
    if re.fullmatch(r'https?://\S+',t,re.I):title_usable=False
    body_usable=len(re.findall(r'[^\W\d_]',b,flags=re.U))>=25
    pending_template=('cheminform is a weekly abstracting service' in b.lower() or
        'wydawnictwo sigma-not wydaje czasopisma fachowe' in b.lower())
    if pending_template:flags.append('unresolved_known_template')
    if not usable:quality='unusable_original'
    elif doi and not body_usable:quality='insufficient_metadata'
    elif meta:quality='nonresearch_editorial'
    elif not title_usable and not body_usable:quality='insufficient_metadata'
    elif pending_template:quality='unresolved_template'
    elif any(x.endswith('_removed') for x in flags):quality='cleaned_title_only' if not body_usable else 'cleaned_text'
    else:quality='title_only' if not body_usable else 'usable_text'
    return dict(title=t,body=b,quality=quality,flags=flags,text_changed=t!=original_t or b!=original_b,
        substantive_title=title_usable,substantive_body=body_usable)
