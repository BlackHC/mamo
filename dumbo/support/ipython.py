from IPython import get_ipython
from IPython.core.magic import Magics, magics_class, cell_magic
from IPython.core.magic_arguments import argument, magic_arguments, parse_argstring
from dumbo.internal import main


@magics_class
class DumboMagics(Magics):
    @cell_magic
    @magic_arguments()
    @argument('name', type=str, nargs="?", default=None, help='Optional name of the cell.')
    def dumbo(self, line, cell):
        "dumbo cell wrapper, only tracks global stores!"
        assert isinstance(line, str)
        assert isinstance(cell, str)
        args = parse_argstring(self.dumbo, line)
        main.dumbo.run_cell(cell, args.name, self.shell.user_ns)


get_ipython().register_magics(DumboMagics)
