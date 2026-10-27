import io, json, os, sys, tempfile, unittest
from pathlib import Path
sandbox = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
os.environ['PHOTO_PORTAL_DB'] = str(Path(sandbox.name) / 'test.db')
os.environ['PHOTO_PORTAL_UPLOADS'] = str(Path(sandbox.name) / 'photos')
sys.path.insert(0, str(Path(__file__).resolve().parent))
from application import app, DBSession, PhotoData, PHOTO_FOLDER, engine

class PortalTests(unittest.TestCase):
    def setUp(self):
        self.admin = app.test_client()
        self.general = app.test_client()
        self.admin.post('/login', data={'username':'admin','password':'classroom'})
        self.general.post('/login', data={'gmail':'viewer@gmail.com'})
        with DBSession() as db:
            db.query(PhotoData).delete(); db.commit()
        for file in PHOTO_FOLDER.iterdir(): file.unlink()
    def upload(self, content=b'original'):
        return self.admin.post('/upload', data={'photo_name':(io.BytesIO(content),'tower.png'), 'date_taken':'10/27/2026','tags':'UT, tower'})
    def test_empty_and_missing_api(self):
        self.assertEqual(self.general.get('/photos').json, {'photos':[]})
        self.assertEqual(self.general.get('/photos/missing.png/tags').json, {'tags':''})
    def test_upload_and_duplicate_does_not_overwrite(self):
        self.assertEqual(self.upload().status_code, 200)
        self.assertIn(b'Photo tower.png already exists.', self.upload(b'replacement').data)
        self.assertEqual((PHOTO_FOLDER/'tower.png').read_bytes(), b'original')
        rows = self.general.get('/photos').json['photos']
        self.assertEqual(len(rows), 1)
        self.assertEqual(json.loads(rows[0])['tags'], 'UT, tower')
    def test_update_and_delete_visible_to_existing_general_session(self):
        self.upload()
        result = self.admin.post('/update_tags', data={'photo_name':'tower.png','new_tags':"Burnt orange, student's photo"})
        self.assertIn(b'updated successfully',result.data)
        self.assertEqual(self.general.get('/photos/tower.png/tags').json['tags'], "Burnt orange, student's photo")
        result = self.admin.post('/delete_photos',data={'photo_name':'tower.png'})
        self.assertIn(b'deleted successfully',result.data)
        self.assertEqual(self.general.get('/photos').json, {'photos':[]})
        self.assertFalse((PHOTO_FOLDER/'tower.png').exists())
    def test_general_and_anonymous_cannot_modify(self):
        for client in [self.general,app.test_client()]:
            for endpoint in ['/upload','/update_tags','/delete_photos']:
                self.assertEqual(client.post(endpoint).status_code,403)
    def test_role_specific_rendering(self):
        self.upload()
        self.assertIn(b'type="radio"',self.admin.get('/gallery').data)
        page=self.general.get('/gallery').data
        self.assertNotIn(b'type="radio"',page)
        self.assertNotIn(b'id="delete-photo"',page)
    def test_empty_tags_replace_existing_tags(self):
        self.upload()
        self.admin.post('/update_tags', data={'photo_name':'tower.png','new_tags':''})
        self.assertEqual(self.general.get('/photos/tower.png/tags').json, {'tags':''})

def tearDownModule():
    engine.dispose()
    sandbox.cleanup()

if __name__ == '__main__': unittest.main(verbosity=2)


