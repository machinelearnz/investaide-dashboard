from builtins import str
import urllib.request, urllib.parse, urllib.error
from bs4 import BeautifulSoup
import ssl
import re
from selenium import webdriver

# Ignore SSL certificate errors2
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

url = 'http://www.bseindia.com/corporates/results.aspx?Code=507685&Company=WIPRO&LTD.&qtr=95.00&RType=D'
#url = 'http://www.bseindia.com/corporates/results.aspx?Code=500209&Company=INFOSYS&LTD.&qtr=95.00&RType=D'
url = 'http://www.bseindia.com/corporates/Results.aspx?Code=500247&Company=KOTAK&MAHINDRA&BANK&LTD.&qtr=91.00&RType=D'
url = "http://www.bseindia.com/corporates/Results.aspx?Code=533155&Company=Jubilant+FoodWorks+Ltd&qtr=95.00&RType="
url = "http://www.bseindia.com/corporates/Results.aspx?Code=500480&Company=CUMMINS+INDIA+LTD.&qtr=95.00&RType=D"
url = 'http://www.bseindia.com/corporates/results.aspx?Code=500209&Company=INFOSYS&LTD.&qtr=93.50&RType=D'
url = 'http://www.bseindia.com/corporates/Results.aspx?Code=533155&Company=Jubilant&FoodWorks&Ltd&qtr=93.50&RType=D'
url = "http://www.bseindia.com/corporates/results.aspx?Code=539871&Company=Thyrocare+Technologies+Ltd&qtr=93.50&RType=D"
url = "http://www.bseindia.com/corporates/results.aspx?Code=538835&Company=Intellect+Design+Arena+Ltd&qtr=95.00&RType=D"
url = "http://www.bseindia.com/corporates/results.aspx?Code=500420&Company=TORRENT+PHARMACEUTICALS+LTD.&qtr=93.50&RType=D"
url = "http://www.bseindia.com/corporates/results.aspx?Code=532540&Company=TATA%20CONSULTANCY%20SERVICES%20LTD.&qtr=91.00&RType=D"
#url = "http://www.bseindia.com/corporates/results.aspx?Code=532331&Company=AJANTA+PHARMA+LTD.&qtr=95.00&RType=D"
url = "http://www.bseindia.com/corporates/Results.aspx?Code=500247&Company=KOTAK&MAHINDRA&BANK&LTD.&qtr=95.00&RType=D"
url = "http://www.bseindia.com/corporates/results.aspx?Code=500875&Company=ITC%20LTD.&qtr=96.00&RType=D"
url = "http://www.bseindia.com/corporates/results.aspx?Code=500820&Company=ASIAN%20PAINTS%20LTD.&qtr=95.00&RType=D"
url = "http://www.bseindia.com/corporates/Results.aspx?Code=539524&Company=Dr.&Lal&PathLabs&Ltd&qtr=96.00&RType=D"
url = "https://www.bseindia.com/corporates/results.aspx?Code=532281&Company=HCL%20TECHNOLOGIES%20LTD.&qtr=96.00&RType=D"
url = 'http://www.bseindia.com/corporates/results.aspx?Code=500209&Company=INFOSYS&LTD.&qtr=97.50&RType=D'

#fh = open(url, 'r')
start_num = float(re.search("qtr=([0-9\.]+)&", url).group(1))

# user 1 for annual and 4 for quarter

ann = 1
opfh = open("output.csv", "w")
opfh2 = open("output2.csv", "w")

prd = 3

optable = dict()
key1 = 0
for count in list(range(0,prd*ann)):

    key1 = count
    optable[key1] = {}


    print("Range :",count)

    if ann == 4:
        count2 = start_num -prd*ann + 1 + count*4/ann
    else :
        count2 = start_num -prd*4 + 4 + count*4/ann


    strcon = "%.2f" % count2
    url = re.sub("qtr=[0-9\.]+", "qtr="+strcon, url)
    print(url)
    bwsr = webdriver.Chrome()
    print("Retreiving :", url)
    bwsr.get(url)
    bwsr.find_element_by_link_text("Consolidated").click()

    #url = re.sub("&[0-9]+\.","&count\.", url)
    #fh = urllib.request.urlopen(url, context=ctx).read()
    #soup = BeautifulSoup(fh, 'html.parser')
    soup = BeautifulSoup(bwsr.page_source, 'html.parser')
    bwsr.quit()
    #tabletag = list(clist6.find_all('table'))
    tabletag = soup.find_all('table', id="ctl00_ContentPlaceHolder1_tbl_typeID")

    try:
        rdata = tabletag[0].find_all('tr')
        print("Reading data ...")
    except:
        print("Not Able to read data, exit read loop")
        break



    for row in rdata:
        tdata = row.find_all('td')
        count =0
        for lst in tdata:

            count = count +1
            #print("^^^^", lst.text, key1)
            if count ==1 :
                if lst.text is "":
                    key2 = "Empty"
                else:
                    key2 = lst.text.replace(",","").title().strip()

            optable[key1].update({key2: lst.text.replace(",","").title().strip() })

            opfh.write(lst.text.replace(",","")+",")

        opfh.write("\n")

    #print("**** ", len(tdata))
    opfh.write("\n")

#print("!!!", type(optable))

blist = []
for entry in optable:
    for ent in optable[entry]:
        blist.append(ent)

ulist = []
for item in blist:
    if item not in ulist:
        ulist.append(item)

hdr_lst =["HEAD"]
inc_lst =["INCOME"]
exp_lst =["EXP"]
tax_lst =["TAX"]
oth_lst =["OTH"]
fin_lst =["FIN"]
dna_lst =["DNA"]
fot_lst =["FOOT"]
pft_lst = ["PROFIT"]

def fwdinstr(low, strg) :
    found = 0
    for wrd in low:
        if wrd in strg:
            found = 1
            break
    return found

for item in ulist:
    print("@@@@", item)
    if fwdinstr (["Sale","Income"], item):
        inc_lst.append(item)
        print("inc")
    elif fwdinstr(["Profit"], item):
        pft_lst.append(item)
        print("pft")
    elif fwdinstr(["Finance", "Interest"], item):
        fin_lst.append(item)
        print("fin")
    elif fwdinstr(["Deprec", "Amorti"], item):
        dna_lst.append(item)
        print("dna")
    elif("Tax") in item:
        tax_lst.append(item)
        print("tax")
    elif fwdinstr(["Expense", "Purchase" , "Consume", "Stock", "Cost", "Expenditure"], item):
        exp_lst.append(item)
        print("exp")
    elif fwdinstr(["Date Begin", "Type" ,"Date End" ,"Description"],item):
        hdr_lst.append(item)
        print("hdr")
    elif fwdinstr(["Empty", "Sharehold", "Basic & Dilut", "Promoter","Non-Encumber", "Face Value", "Equity Capital", "Share Capital"], item):
        fot_lst.append(item)
        print("fot")
    else:
        oth_lst.append(item)
        print("oth")

flist = []
flist = hdr_lst + inc_lst + exp_lst + dna_lst + fin_lst + tax_lst + pft_lst + oth_lst + fot_lst


print("!!!!", len(blist),len(ulist), len(flist))
for item in flist:
    opfh2.write(item +",")
    for prd_data in optable:
        if item in optable[prd_data]:
            opfh2.write(optable[prd_data][item]+",")
        else:
            opfh2.write(",")
    opfh2.write("\n")



opfh.close()
opfh2.close()
