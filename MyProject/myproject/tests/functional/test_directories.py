from myproject.tests import *

class TestDirectoriesController(TestController):
    def test_index(self):
        response = self.app.get(url_for(controller='directories'))
        # Test response...