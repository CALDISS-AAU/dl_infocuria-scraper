from bs4 import BeautifulSoup as bs
import requests
import time
import re
import random 
from datetime import datetime
import os
import json

# Setting default path for saving data
data_path = os.path.join('..', 'data')

if os.path.isdir(data_path) == False:
    os.mkdir(data_path)

# Format strings for curia
DOC_HTML_FORMAT = "http://curia.europa.eu/juris/document/document_print.jsf?docid={}&text=&doclang={}"
DOC_PDF_FORMAT = "http://curia.europa.eu/juris/showPdf.jsf?docid={}&doclang={}"
RESULTS_FORMAT ="http://curia.europa.eu/juris/documents.jsf?page={}&cid={}"

# Main search URL: Judgements for Court of Justice and Grand Chamber, closed cases.
SEARCH_URL = "http://curia.europa.eu/juris/documents.jsf?mat=or&lgrec=en&jur=C%2CT&etat=clot&pcs=Oor&nat=or&td=%3B%3B%3BPUB1%3BNPUB1%3B%3B%3BORDALL"


# Defining function

def get_cid(soup):
    """
    Returns the "cid" for the search session. The cid is needed for pagination in the search results. Takes a InfoCuria search result as a soup object as arguement.
    """
    paginate_link = soup.find('div', class_ = 'pagination').find('a')['href']
    cid_re = re.compile('(?<=cid\=)\d{5,12}$')
    cid = cid_re.findall(paginate_link)[0]
    
    return(cid)


def get_last_page(soup):
    """
    Returns the last page number of search results. Takes a InfoCuria search result as a soup object as arguement.
    """
    paginate_text = soup.find('div', class_ = 'pagination').get_text()
    num_re = re.compile('\d{1,5}(?=\sPages)')
    last_page = num_re.findall(paginate_text)[0]
    
    return(last_page)

def get_docids(soup): # Currently only retrieves ids for documents with html
    """
    (not used) Returns all docids from a search result page. Takes a InfoCuria search result as a soup object as arguement.
    """
    doc_divs = soup.find_all('div', id = 'docHtml')
    num_re = re.compile('\d*(?=\w)')
    
    docids = [num_re.findall(div.find('img')['id'])[0] for div in doc_divs]
    
    return(docids)
    
    
def get_docid(row):
    """
    Returns the docid from a search result. Takes a table row of InfoCuria search results as a soup object as arguement.
    """
    num_re = re.compile('\d*(?=\w)')
    docid = num_re.findall(row.find('td', class_ = 'table_cell_links_eurlex').find('img')['id'])[0]
    
    return(docid)


def get_docurl(docid, docformat, doclang = 'en', in_english = True):
    """
    Formats a URL to download a CJEU document based on docid and docformat ('docHtml' or 'docPdf'). NOTE: Currently only works on English documents.
    """
    
    if in_english == False:
        return
    
    if doclang != 'en':
        raise ValueError("'{}' is not a valid doc language. Function only supports doclang = 'en'")
    
    if docformat == 'docHtml':
        docurl = DOC_HTML_FORMAT.format(docid, doclang)
    elif docformat == 'docPdf':
        docurl = DOC_PDF_FORMAT.format(docid, doclang)
    else:
        raise ValueError("'{}' is not a valid format. Use either 'docHtml' or 'docPdf'.".format(docformat))
    
    return(docurl)


def get_rowdata(row):
    """
    Compiles document data from a search result based on a row in the table of InfoCuria results. Takes a table row of InfoCuria search results as a soup object as arguement. Returns a dictionary.
    """    
    doc_dict = {}

    keys = ['case', 'document type', 'document date', 'name of parties', 'subject-matter']
    class_suffixes = ['aff', 'doc', 'date', 'nom_usuel', 'links_curia']

    for key, class_suf in zip(keys, class_suffixes):
        doc_dict[key] = row.find('td', class_ = 'table_cell_{}'.format(class_suf)).get_text(strip = True)

    doc_dict['format'] = row.find('td', class_ = 'table_cell_links_eurlex').find('div')['id']
    doc_dict['docid'] = get_docid(row)
    doc_dict['in english'] = "English" in row.find('td', class_ = 'table_cell_links_eurlex').find('div', id = re.compile(doc_dict['docid'])).get_text().split('\n')
    doc_dict['docurl'] = get_docurl(doc_dict['docid'], doc_dict['format'], in_english = doc_dict['in english'])
    doc_dict['retrieval date'] = str(datetime.now().date())
    
    return(doc_dict)


def dl_doc(docid, url, docformat, savedir = data_path, with_print = True):
    """
    Downloads a InfoCuria document based on docid, url and docformat ('docHtml', 'docPdf').
    """
    
    if os.path.isdir(data_path) == False:
        os.mkdir(data_path)
    
    r = requests.get(url)
    
    if docformat == 'docPdf':
        docpdf = r.content
        pdf_path = os.path.join(savedir, 'pdf')
        if os.path.isdir(pdf_path) == False:
            os.mkdir(pdf_path)
        
        file_path = os.path.join(pdf_path, 'cjeu{}.pdf'.format(docid))
               
        with open(file_path, 'wb') as f:
            f.write(docpdf)
            
    elif docformat == 'docHtml':
        dochtml = r.text
        html_path = os.path.join(savedir, 'html')
        if os.path.isdir(html_path) == False:
            os.mkdir(html_path)
        
        file_path = os.path.join(html_path, 'cjeu{}.html'.format(docid))
        
        with open(file_path, 'w', encoding = 'utf-8') as f:
            f.write(dochtml)
    else:
        raise ValueError("'{}' is not a valid format. Use either 'docHtml' or 'docPdf'.".format(docformat))
    
    if with_print:
        print('Docid {} succesfully downloaded as {} to path {}'.format(docid, docformat, file_path))
  
  
# Collect data from search results (stored as JSON). NOTE: Does not check for existing data.
session = requests.session()

response = session.get(SEARCH_URL)
search_soup = bs(response.content, 'html.parser')

last_page = int(get_last_page(search_soup))
cid = get_cid(search_soup)

docs = list()

for pageno in range(1, last_page + 1):
    print("Retrieving page {}/{}".format(pageno, last_page), end = "\r")
    page_response = session.get(RESULTS_FORMAT.format(pageno, cid))
    page_soup = bs(page_response.content, 'html.parser')
    
    for row in page_soup.find('tbody').find_all('tr', recursive = False):
        row_dict = get_rowdata(row)
        docs.append(row_dict)
        
session.close()

with open(os.path.join(data_path, 'cjeu_docs.json'), 'w', encoding = 'utf-8') as f:
    json.dump(docs, f)


# Opens existing data from search results. NOTE: Overwrites previous docs object. Use either the lines below or create new data set.        
with open('../data/cjeu_docs.json', 'r') as f:
    docs = json.load(f)
    
# Download documents. Skips existing documents.
for c, cjdoc in enumerate(docs, start = 1):
    if cjdoc['docurl'] is None:
        continue
    
    file_path_html = os.path.join(data_path, 'html', 'cjeu{}.html'.format(cjdoc['docid']))
    file_path_pdf = os.path.join(data_path, 'pdf', 'cjeu{}.pdf'.format(cjdoc['docid']))
    
    if not (os.path.isfile(file_path_html) or os.path.isfile(file_path_pdf)):
        dl_doc(docid = cjdoc['docid'], url = cjdoc['docurl'], docformat = cjdoc['format'], with_print = False)
        
        sleep_time = random.uniform(0.5, 1.5)
        time.sleep(sleep_time)
        
    print("{:.2f}% of documents downloaded".format(100.0*c/len(docs)), end = "\r")    