from IPython import get_ipython
from IPython.core.magic import Magics, magics_class, cell_magic
from dumbo.internal import main


@magics_class
class DumboMagics(Magics):
    @cell_magic
    def dumbo(self, line, cell):
        "dumbo cell wrapper, only tracks global stores!"
        assert isinstance(line, str)
        assert not line
        assert isinstance(cell, str)
        main.dumbo.run_cell(cell, self.shell.user_ns)


get_ipython().register_magics(DumboMagics)
