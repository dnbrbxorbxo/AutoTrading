import re
import pdfplumber
import pandas as pd

def extract_text_from_pdf(pdf_path):
    """
    pdfplumber를 사용하여 PDF 파일에서 텍스트를 추출하고 페이지 번호를 반환합니다.
    """
    text_data = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            # 각 페이지에서 텍스트 추출
            page_text = page.extract_text()
            if page_text:
                # 텍스트 데이터에 페이지 번호와 텍스트를 추가
                text_data.append((page_number, page_text.strip()))
    return text_data

def parse_text_to_sections_and_paragraphs(text_data):
    """
    추출된 텍스트를 구조화된 섹션 및 문단으로 파싱하여 페이지 번호를 포함시킵니다.
    """
    # 섹션 패턴 정의
    section_pattern = re.compile(r'((?:IX|IV|V?I{0,3})\.\s+.*?|\d+\.\s+.*?|\d+\.【.*?】.*?)(?=\n|\Z)', re.DOTALL)

    parsed_data = []
    paragraphs = text_data.split("\n")
    current_section = None
    current_content = []

    for paragraph in paragraphs:
        if section_pattern.match(paragraph):
            if current_section:
                # 이전 섹션 저장
                parsed_data.append((current_section.strip(), " ".join(current_content).strip()))
            # 새로운 섹션 시작
            current_section = paragraph
            current_content = []
        else:
            # 섹션 내용 추가
            current_content.append(paragraph)

    # 마지막 섹션 저장
    if current_section:
        parsed_data.append((current_section.strip(), " ".join(current_content).strip()))

    return parsed_data

def text_data_to_dataframe(text_data):
    """
    추출된 텍스트 데이터를 pandas DataFrame으로 변환합니다.
    """
    df = pd.DataFrame(text_data, columns=['페이지 번호', '텍스트'])
    return df

# 파일 경로 정의
pdf_path = './target.pdf'  # PDF 파일 경로로 변경

# 텍스트 추출
text_data = extract_text_from_pdf(pdf_path)

# 텍스트 데이터를 pandas DataFrame으로 변환
df = text_data_to_dataframe(text_data)

# 섹션 및 문단으로 분리된 데이터 저장할 리스트
parsed_data = []

# 각 페이지의 텍스트에 대해 섹션 및 문단으로 파싱하여 저장
for index, row in df.iterrows():
    page_number = row['페이지 번호']
    text = row['텍스트']
    parsed_sections = parse_text_to_sections_and_paragraphs(text)
    for section, content in parsed_sections:
        parsed_data.append((page_number, section, content))

# DataFrame으로 변환
parsed_df = pd.DataFrame(parsed_data, columns=['페이지 번호', '섹션', '내용'])

# DataFrame을 엑셀 파일로 저장
excel_path = './result.xlsx'
parsed_df.to_excel(excel_path, index=False)
print(f"데이터가 {excel_path}로 추출되고 내보내졌습니다.")
