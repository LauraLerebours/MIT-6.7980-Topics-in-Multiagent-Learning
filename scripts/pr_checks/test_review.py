import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image, ImageDraw
from html_diff import changed_blocks, panels
from html_review import classify

spec=importlib.util.spec_from_file_location('quality_publisher',Path(__file__).with_name('publish.py'))
publisher=importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


class DiffTests(unittest.TestCase):
    def block(self,key,top,bottom):
        return dict(key=key,top=top,bottom=bottom,styles=[])

    def test_insertion_does_not_mark_shifted_following_paragraph_deleted(self):
        old=Image.new('RGB',(100,100),'white')
        new=Image.new('RGB',(100,150),'white')
        a=[self.block('X',0,20),self.block('Y',70,90)]
        b=[self.block('X',0,20),self.block('added',30,60),self.block('Y',120,140)]
        self.assertEqual(changed_blocks({'blocks':a},{'blocks':b},old,new),[(1,1,1,2)])

    def test_figure_pixels_change_even_with_identical_caption(self):
        a=Image.new('RGB',(100,100),'white')
        b=a.copy();ImageDraw.Draw(b).rectangle((10,10,60,60),fill='red')
        blocks={'blocks':[self.block('caption',0,100)]}
        self.assertEqual(changed_blocks(blocks,blocks,a,b),[(0,1,0,1)])

    def test_continuation_uses_single_column(self):
        with tempfile.TemporaryDirectory() as tmp:
            regions=panels(Image.new('RGB',(100,100),'white'),Image.new('RGB',(100,3000),'white'),Path(tmp),'test',dict(page='x.html',viewport=390))
            self.assertEqual(len(regions),3)
            with Image.open(Path(tmp)/regions[1]['file']) as image:
                self.assertLess(image.width,200)

    def test_only_exact_baseline_findings_are_downgraded(self):
        def f(side,message):
            return dict(side=side,code='overflow',page='x.html',viewport=390,level='error',message=message)
        findings=classify([f('before','old'),f('after','old'),f('after','new')])
        self.assertEqual([x['level'] for x in findings],['warning','error'])


class PublicationTests(unittest.TestCase):
    def test_rejects_wrong_commit_and_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            report=dict(version=1,pr=1,base='a'*40,head='b'*40,kind='html',findings=[],checks=[],regions=[])
            (folder/'report.json').write_text(json.dumps(report))
            with self.assertRaises(ValueError):publisher.validate(folder,1,'a'*40,'c'*40,'html')
            report['regions']=[dict(file='../outside.png')]
            (folder/'report.json').write_text(json.dumps(report))
            with self.assertRaises(ValueError):publisher.validate(folder,1,'a'*40,'b'*40,'html')

    def test_sanitizes_mentions_and_markup(self):
        value=publisher.clean('<script>@all [link](evil)</script>')
        self.assertNotIn('<script>',value)
        self.assertNotIn('@all',value)
        self.assertNotIn('[link]',value)


if __name__=='__main__':unittest.main()
