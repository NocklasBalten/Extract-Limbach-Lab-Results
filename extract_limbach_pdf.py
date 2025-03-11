import sys
import json
from pdfminer.converter import PDFPageAggregator
from pdfminer.layout import LAParams, LTTextBoxHorizontal
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument

def main():
    
    # Validate the pdf_path and output_path
    if len(sys.argv) != 3:
        print("Usage: extract_limbach_pdf.py [input.pdf] [output.txt]")
        sys.exit(1)

    input_path = sys.argv[1]
    if input_path[-4:] != '.pdf':
        print("Error: The input file must be a PDF file.")
        sys.exit(1)

    output_path = sys.argv[2]
    if output_path[-5:] != '.json':
        print("Error: The output file must be a JSON file.")
        sys.exit(1)

    lab_results = [] # list of json formatted outputs per page

    with open(input_path, 'rb') as in_file:

        # Parse and read the PDF file
        parser = PDFParser(in_file)
        doc = PDFDocument(parser)
        rsrcmgr = PDFResourceManager()
        device = PDFPageAggregator(rsrcmgr, laparams=LAParams())
        interpreter = PDFPageInterpreter(rsrcmgr, device)        
        for page in PDFPage.create_pages(doc):
            interpreter.process_page(page)
            layout = device.get_result()

            # Initialize text_lines of entire page
            text_lines = []
            for element in layout:
                if isinstance(element, LTTextBoxHorizontal):
                    for text_line in element:
                        text_lines.append(text_line)

            # Extract patient infos and lab results

            # Initialize json_output
            lab_result = {} # json formatted output per page
            lab_result["Parameters"] = [] # Ensure "Parameters" is a list

            for text_line in text_lines:
                x0, y0, _, _ = text_line.bbox  # Coordinates of the text

                if y0 >= 514 and y0 <= 515:  # Check if the text is in the range of the patient infos
                    lab_result.update(extract_patient_infos(text_line, x0))

                elif y0 < 461:  # Check if the text is in the range of the lab results, beneath "Untersuchung"
                    parameter = extract_lab_results(text_line, x0, y0, text_lines)

                    # Comments need extra handling because they can span multiple lines

                    if not parameter:
                        continue
                
                    # if parameter is not a comment, its key(s) and value(s) can be added to the previous parameter
                    # in the list of parameters

                    if "Comment" not in parameter:
                        lab_result["Parameters"].append(parameter)
                        continue

                    try:
                        # if the previous parameter already has a comment, append the current comment to it
                        if "Comment" in lab_result["Parameters"][-1]:
                            lab_result["Parameters"][-1]["Comment"] = lab_result["Parameters"][-1]["Comment"] + '\n' + parameter["Comment"]
                        # if the previous parameter does not have a comment, add the current comment to it
                        else:
                            lab_result["Parameters"][-1].update(parameter)
                    # for multi-page lab results, the first parameter may be a comment, which would raise an IndexError
                    except IndexError:
                        lab_result["Parameters"].append(parameter)
                
            lab_results.append(lab_result)

    # clean up the text
    lab_results = json.dumps(lab_results, ensure_ascii=False, indent = 4) # json formatted output
    lab_results = lab_results.replace('(cid:13)', '')

    with open(output_path, 'w') as output_file:
        output_file.write(lab_results)

def extract_patient_infos(text_line, x0):
    output = {}
    if x0 >= 55 and x0 <= 56:
        name_split = text_line.get_text().strip().split(',') # splits the name at the comma
        if len(name_split) == 2:
            firstname = name_split[1].strip() # strips the whitespace after the comma
            surname = name_split[0]
            output["Vorname"] = firstname
            output["Nachname"] = surname
        else:
            return 1

    elif x0 >= 361 and x0 <= 362:
        birth_gender = text_line.get_text().strip()
        birth_gender_split = birth_gender.split('/')
        if len(birth_gender_split) == 2:
            birthday = birth_gender_split[0].strip() #strips the whitespace before the slash
            gender = birth_gender_split[1].strip() #strips the whitespace after the slash
            output["Geburtsdatum"] = birthday
            output["Geschlecht"] = gender
    elif x0 >= 464 and x0 <= 465:
        anr = text_line.get_text().strip()[10:] #slices "Ext.-Nr: " from the beginning of the string
        output["ANR"] = anr
    return output

def extract_lab_results(text_line, x0, y0, text_lines):
    output = {}
    if x0 >= 65 and x0 <= 66:
        # differentiate between parameter + value + unit + reference ranges and comments
        for value_unit_line in text_lines:
            value_unit_x0, value_unit_y0, _, _ = value_unit_line.bbox

            # if there is a (value_unit_)line on a similar y-coordinate and to the right of the text_line, 
            # text_line is a parameter and value_unit_line is the value + unit

            if int (value_unit_y0) in range(int (y0 - 5), int (y0 + 5)) and value_unit_x0 > x0: 

                # text_line is a parameter in this case
                parameter = text_line.get_text().strip()
                output["Parameter"] = parameter

                value_unit = value_unit_line.get_text().strip()
                value_unit_split = value_unit.split(' ')
                if len(value_unit_split) == 2:
                    value = value_unit_split[0]
                    unit = value_unit_split[1]
                else:
                    value = value_unit
                    unit = None

                output["Value"] = value
                output["Unit"] = unit

                # check for reference ranges
                # if there is a (reference_range_)line on a similar y-coordinate and to the right of the 
                # value_unit_line, value_unit_line is the value + unit and reference_range_line is the reference range

                for reference_range_line in text_lines:
                    reference_range_x0, reference_range_y0, _, _ = reference_range_line.bbox
                    if int (reference_range_y0) in range(int (value_unit_y0 - 5), int (value_unit_y0 + 5)) and reference_range_x0 > value_unit_x0:
                        reference_range = reference_range_line.get_text().strip()
                        output["Reference_Range"] = reference_range
                        return output
                output["Reference_Range"] = None
              #  output = (f"{output}Reference Range: {reference_range}\n")
                return output
    
        # if the text is not a parameter, it is a comment
        
        comment = text_line.get_text().strip()
        output["Comment"] = comment

    return output

main()