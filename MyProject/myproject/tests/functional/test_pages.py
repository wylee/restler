from myproject.tests import *

class TestPagesController(TestController):
    def test_index(self):
        response = self.app.get(url_for(controller='pages'))
        # Test response...