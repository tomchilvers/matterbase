import pytest
from text_recognition import ocr_lines, recognise_identity


def line(text, x, y, w, h, confidence=95):
    return {"text": text, "x": x, "y": y, "w": w, "h": h, "confidence": confidence,
            "words": [{"text": word, "confidence": confidence} for word in text.split()]}


def test_mixed_products_are_assigned_to_their_own_columns():
    lines = [line('KAJPLATS KIT ~', 770, 550, 500, 60),
             line('KAJPLATS', 1400, 520, 430, 80),
             line('IKEA', 1150, 1100, 50, 20),
             line('command', 780, 150, 150, 24),
             line('Design and Quality', 1000, 1150, 200, 20),
             line('Blas', 100, 900, 40, 20, 22)]
    codes = [{'_bounds':[300,540,80,80]}, {'_bounds':[876,678,83,82]},
             {'_bounds':[871,825,84,86]}, {'_bounds':[1444,682,84,80]}]
    result = recognise_identity(lines, codes, (2048,1536))
    assert result['brand'] == 'IKEA'
    assert set(result['products']) == {'KAJPLATS', 'KAJPLATS KIT'}
    assert result['product'] == ''
    assert [code['product'] for code in codes] == ['', 'KAJPLATS KIT', 'KAJPLATS KIT', 'KAJPLATS']
    assert all(code['brand']=='IKEA' and '_bounds' not in code for code in codes)


def test_one_product_and_brand_fill_unpositioned_printed_codes():
    codes = [{'manual_code':'34970112332'}]
    result = recognise_identity([line('Philips Hue',20,20,150,30),line('White Ambiance',20,80,200,40)],codes,(600,400))
    assert result['brands'] == ['Philips Hue']
    assert codes[0]['brand']=='Philips Hue' and codes[0]['product']=='White Ambiance'


def test_low_confidence_brand_and_product_remain_blank():
    code = {'_bounds':[50,150,80,80]}
    result = recognise_identity([line('IKEA',50,50,150,40,20),line('KAJPLATS',50,90,200,40,30)],[code],(500,400))
    assert result['brands'] == result['products'] == []
    assert code['brand'] == code['product'] == ''


def test_multiple_brands_do_not_silently_apply_one_to_every_device():
    code = {}
    result = recognise_identity([line('IKEA',10,10,100,40),line('Aqara',300,10,100,40)],[code],(500,400))
    assert set(result['brands']) == {'IKEA','Aqara'}
    assert code['brand']==''


def test_brand_prefix_is_split_from_product_name():
    code = {}
    recognise_identity([line('IKEA KAJPLATS',10,10,300,50)],[code],(500,400))
    assert code['brand']=='IKEA' and code['product']=='KAJPLATS'


def test_ocr_lines_group_words_and_keep_bounds_confidence():
    data = {'text':['','KAJPLATS','KIT'], 'conf':[-1,90,80],
            'left':[0,30,180], 'top':[0,20,24], 'width':[500,140,50], 'height':[400,35,30],
            'block_num':[0,1,1], 'par_num':[0,1,1], 'line_num':[0,1,1]}
    lines = ocr_lines(data)
    assert len(lines)==1 and lines[0]['text']=='KAJPLATS KIT'
    assert (lines[0]['x'],lines[0]['y'],lines[0]['w'],lines[0]['h']) == (30,20,200,35)
    assert 80 < lines[0]['confidence'] < 90

@pytest.mark.parametrize('heading,expected',[('KAJ PLATS','KAJPLATS'),('KAJ PLATS KIT','KAJPLATS KIT')])
def test_split_ikea_heading_is_normalised(heading,expected):
    code={}
    result=recognise_identity([line(heading,10,10,300,50),line('IKEA of Sweden',10,300,200,20)],[code],(600,400))
    assert result['brand']=='IKEA' and code['product']==expected


def test_second_ocr_pass_recovers_fragmented_text(monkeypatch):
    import io
    import scanner
    from PIL import Image
    def data(words):
        return {'text':words,'conf':[95]*len(words),'left':[10]*len(words),'top':[20+i*80 for i in range(len(words))],
                'width':[200]*len(words),'height':[40]*len(words),'block_num':list(range(len(words))),
                'par_num':[1]*len(words),'line_num':[1]*len(words)}
    passes=[]
    def recognise(image,**kwargs):
        passes.append(kwargs['config'])
        return data(['ve','hed','B|KE']) if len(passes)==1 else data(['KAJ PLATS','IKEA of Sweden','0005-491-2336'])
    monkeypatch.setattr(scanner.shutil,'which',lambda _: '/usr/bin/tesseract')
    monkeypatch.setattr(scanner.pytesseract,'image_to_data',recognise)
    image=io.BytesIO();Image.new('RGB',(500,600),'white').save(image,format='PNG')
    result=scanner.scan_image(image.getvalue())
    assert passes==['--psm 11','--psm 3']
    assert result['identity']['brand']=='IKEA' and result['identity']['product']=='KAJPLATS'
    assert result['codes'][0]['product']=='KAJPLATS'
