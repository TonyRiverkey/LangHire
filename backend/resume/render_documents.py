"""Readable application documents from reviewed text; source PDF remains untouched."""
from xml.sax.saxutils import escape

from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer


def styles():
    s=getSampleStyleSheet()
    s.add(ParagraphStyle(name='Body',fontName='Helvetica',fontSize=9.5,leading=12,spaceAfter=4))
    s.add(ParagraphStyle(name='ApplicationBullet',parent=s['Body'],leftIndent=9,firstLineIndent=-7))
    s.add(ParagraphStyle(name='Role',parent=s['Body'],fontName='Helvetica-Bold',spaceBefore=5,keepWithNext=True))
    s.add(ParagraphStyle(name='RoleDate',parent=s['Body'],keepWithNext=True))
    s['Heading2'].fontName='Helvetica-Bold';s['Heading2'].fontSize=11;s['Heading2'].spaceBefore=7;s['Heading2'].spaceAfter=5
    s['Title'].fontSize=21;s['Title'].leading=24
    return s


def render_resume(sections,edits,name,contact,path):
    s=styles(); story=[Paragraph(escape(name),s['Title']),Paragraph(escape(contact),s['Body'])]
    last_type=None
    for i,section in enumerate(sections):
        if section['section_type']=='contact':continue
        text=edits.get(i,section['text'])
        if not text.strip():continue
        title=section['title']
        if section['section_type']=='experience':
            title='PROFESSIONAL EXPERIENCE'
            if last_type!='experience':story.append(Paragraph(title,s['Heading2']))
        else:story.append(Paragraph(escape(title),s['Heading2']))
        lines=[line.strip() for line in text.splitlines() if line.strip()]
        index=0
        while index<len(lines):
            line=lines[index]
            if line==title:index+=1;continue
            if section['section_type'] in ('experience','projects') and '|' in line and len(line)<150 and index+1<len(lines) and any(c.isdigit() for c in lines[index+1]):
                # Repeated cross-role headers preserve attribution across source page breaks.
                story.extend([Paragraph(escape(line),s['Role']),Paragraph(escape(lines[index+1]),s['RoleDate'])])
                index+=2;continue
            bullet=line.startswith(('-', '•', '·'))
            story.append(Paragraph(escape(('- '+line.lstrip('-•· ')) if bullet else line),s['ApplicationBullet'] if bullet else s['Body']))
            index+=1
        last_type=section['section_type']
    def footer(canvas,doc):
        canvas.setFont('Helvetica',8);canvas.drawRightString(566,24,str(doc.page))
    SimpleDocTemplate(str(path),pagesize=(612,792),leftMargin=46,rightMargin=46,topMargin=35,bottomMargin=38).build(story,onFirstPage=footer,onLaterPages=footer)


def render_letter(text,profile,job,path):
    s=styles();story=[]
    lines=[profile.get('name',''),profile.get('email',''),job['company'],'Re: '+job['title'],'Dear Hiring Team,']
    for i,line in enumerate(lines):story.append(Paragraph(escape(line),s['Title'] if i==0 else s['Body']))
    story.append(Spacer(1,10))
    for para in text.split('\n\n'):
        story.extend([Paragraph(escape(para),s['Body']),Spacer(1,8)])
    story.extend([Paragraph('Sincerely,',s['Body']),Paragraph(escape(profile.get('name','')),s['Body'])])
    SimpleDocTemplate(str(path),pagesize=(612,792),leftMargin=52,rightMargin=52,topMargin=45,bottomMargin=45).build(story)
