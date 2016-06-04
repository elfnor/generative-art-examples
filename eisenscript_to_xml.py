"""
Translates the eisen script files used by StructureSynth
http://structuresynth.sourceforge.net/reference.php
into the eisenxml files used by the GenerativeArt node of the Sverchok addon for 
Blender
http://elfnor.com/generative-art-sverchok-node-update.html

This translator ignores all commands to do with color or raytacing.
It will fail to translate eisenscript containing preprocessor (#define) commands

It requires the pyparsing module avaliable here:
http://pyparsing.wikispaces.com/Download+and+Installation

Usage:

$ python eisenscript_to_xml.py /path/to/file/totranslate.es

will produce a file

/path/to/file/totranslate.es.xml

"""
import os
import sys
import glob
import itertools
from xml.etree import ElementTree as ET
from xml.dom import minidom
import pyparsing as pp


def trans_str(trans_list):
    """
    x -> tx
    y -> ty
    z -> tz
    rx -> rx
    ry -> ry
    rz -> rz
    s n -> sa n
    s n n n -> s n n n
    """
    tstr = ''
    for t in trans_list:
        if t.tid == 's' and len(t) == 2:
            t.tid = 'sa'
        if t.tid in ('x', 'y', 'z'):
            t.tid = 't' + t.tid

        tstr = tstr + t.tid + ' ' + ' '.join(t.tvalues) + ' '
    tstr = tstr.strip()
    return tstr

# pretty print function for xml


def prettify(elem):
    """Return a pretty-printed XML string for the Element.
    """
    rough_string = ET.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")


def eisen_grammar():
    # define parser grammar
    # this is rough and imposes no structure on float and interger expressions
    # but works if es is properly formed
    fnum = pp.Word(".+-*/()"+pp.nums)
    
    tid = pp.oneOf('x y z s rx ry rz', caseless=True)('tid')
    # these are color transforms that we're ignoring
    cid = pp.oneOf('h hue sat b brightness a alpha m', caseless=True)

    tvalues = pp.OneOrMore(fnum)('tvalues')

    gtrans = pp.Group(tid + tvalues).setResultsName('trans', 
                                                    listAllMatches=True)
    ctrans = cid + tvalues
    c2trans = pp.CaselessKeyword('color') + pp.Word(pp.alphanums + '#')
    c3trans = pp.CaselessKeyword('blend') + pp.Word(pp.alphanums + '#') + fnum
    trans = gtrans | ctrans | c2trans | c3trans

    
    

    rule_name = pp.NotAny(pp.CaselessKeyword('rule')) + \
        pp.Word(pp.alphas, pp.alphanums+'_')

    loop_multiplier = fnum('count') + pp.Suppress('*')
    loop = pp.Group(pp.Optional(loop_multiplier) +
                    pp.Suppress('{') +
                    pp.ZeroOrMore(trans) +
                    pp.Suppress('}')).setResultsName('loop', 
                                                     listAllMatches=True)

    md = pp.oneOf('md maxdepth', caseless=True)
    md_mod = md + fnum('md') + pp.Optional('>' + rule_name('successor_rule'))

    weight = pp.oneOf('w weight', caseless=True)
    w_mod = weight + fnum('wm')
    
    shape_words = pp.oneOf(['box', 'grid', 'sphere', 'line'], caseless=True)
    shape = pp.Combine(shape_words + pp.Optional(pp.Word(pp.alphas + ':')))

    global_md = pp.CaselessKeyword('set') + md \
                                          + fnum('global_md')

    shape_call = (pp.Optional(loop) + 
                  shape('shape')).setResultsName('bcall', listAllMatches=True)
    rule_call = (pp.ZeroOrMore(loop) + 
            rule_name('rule_name')).setResultsName('rcall', listAllMatches=True)
    call = shape_call | rule_call
    rule = pp.Group(pp.Suppress(pp.CaselessKeyword('rule')) +
                    rule_name('name') +
                    (pp.Optional(md_mod) & pp.Optional(w_mod)) +
                    pp.Suppress('{') +
                    pp.OneOrMore(call) +
                    pp.Suppress('}'))

    entry = pp.Group(pp.OneOrMore(call)).setResultsName('entry_calls', 
                                                        listAllMatches=True)
    main = pp.Group(pp.OneOrMore(rule)).setResultsName('rule_defs', 
                                                        listAllMatches=True)
    file_def = pp.Optional(global_md) + entry + main 
    file_def.ignore(pp.cppStyleComment)
    # more stuff to ignore
    set_words = pp.oneOf('seed maxobjects maxsize minsize background ' +
                         'colorpool translation rotation pivot scale ' +
                         'raytracer syncrandom', caseless=True)
    set_ignore = pp.CaselessKeyword('set') + set_words + pp.restOfLine
    file_def.ignore(set_ignore)
    return file_def

# from pyparsing results to xml


def es_call(top, rule, pcall, is_bcall, n):

    if is_bcall:
        call_type = 'instance'
        atr_name = 'shape'
        atr_value = pcall.shape
    else:
        call_type = 'call'
        atr_name = 'rule'
        atr_value = pcall.rule_name[0]

    call = ET.SubElement(rule, call_type)
    # dealing with nested rules
    # assumes single level of nesting (2 loops per call)
    # and only rule calls are nested
    # this code will need refactoring but this is working.
    if len(pcall.loop) == 0:
        call.set('transforms', trans_str(pcall.trans))
        if pcall.count:
            call.set('count', pcall.count)
        call.set(atr_name, atr_value)
    elif len(pcall.loop) == 1:
        call.set('transforms', trans_str(pcall.loop[0].trans))
        if pcall.loop[0].count:
            call.set('count', pcall.loop[0].count)
        call.set(atr_name, atr_value)

    elif len(pcall.loop) > 1:
        # call a sub rule
        newname = atr_value + '_{:02d}'.format(next(n))
        call.set('transforms', trans_str(pcall.loop[0].trans))
        if pcall.loop[0].count:
            call.set('count', pcall.loop[0].count)
        call.set(atr_name, newname)
        # make up a whole new rule
        # rules are sub elements of top
        newrule = ET.SubElement(top, 'rule')
        newrule.set('name', newname)
        newcall = ET.SubElement(newrule, 'call')
        newcall.set('transforms', trans_str(pcall.loop[1].trans))
        if pcall.loop[1].count:
            newcall.set('count', pcall.loop[1].count)
        # call original rule
        newcall.set(atr_name, atr_value)

    return top


def es_xml2(results):
    n = itertools.count()
    top = ET.Element('rules')
    if results.global_md:
        top.set('max_depth', results.global_md)
    else:
        top.set('max_depth', '1000')
    entry = ET.SubElement(top, 'rule')
    entry.set('name', 'entry')
    for p in results.entry_calls:
        for c in p.bcall:
            top = es_call(top, entry, c, True, n)
        for c in p.rcall:
            top = es_call(top, entry, c, False, n)

    for p in results.rule_defs[0]:
        rule = ET.SubElement(top, 'rule')
        rule.set('name', p.name[0])
        if p.wm:
            rule.set('weight', p.wm)
        if p.md:
            rule.set('max_depth', p.md)
        if p.successor_rule:
            rule.set('successor', p.successor_rule[0])
        for c in p.bcall:
            top = es_call(top, rule, c, True, n)
        for c in p.rcall:
            top = es_call(top, rule, c, False, n)

    return top


def translate_eisen(es_filename, xml_dir=''):
    if xml_dir:
        if not os.path.exists(xml_dir):
            os.makedirs(xml_dir)
        base = os.path.basename(es_filename)
        xml_filename = os.path.join(xml_dir, base + '.xml')
    else:    
        xml_filename = es_filename + '.xml'
    file_def = eisen_grammar()
    results = file_def.parseFile(es_filename)
    xml = es_xml2(results)
    xml_file = open(xml_filename, 'w')
    xml_file.write(prettify(xml))
    xml_file.close()
    
def test_examples():
    es_dir = '/usr/share/structure-synth/Examples/'
    xml_dir = os.path.join(os.path.curdir, 'xml_translate')
    for name  in  glob.glob(es_dir + '*' + '.es'):
        print(name)
        try:
            translate_eisen(name, xml_dir )
        except:
            print('failed')

if __name__ == "__main__":    
    try:
        translate_eisen(sys.argv[1])
    except IndexError:
        print('usage: python eisenscript_to_xml.py /path/to/file/totranslate.es')
    except pp.ParseException:
        print("I don't understand the eisenscript")
    


        
        


            