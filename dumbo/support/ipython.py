from IPython import get_ipython
from IPython.core.magic import Magics, magics_class, cell_magic
from IPython.core.magic_arguments import argument, magic_arguments, parse_argstring
import dumbo


@magics_class
class DumboMagics(Magics):
    @cell_magic
    @magic_arguments()
    @argument("name", type=str, default=None, help="Name of the cell.")
    def dumbo(self, line, cell_code):
        """dumbo cell wrapper, only tracks global stores!"""
        assert isinstance(line, str)
        assert isinstance(cell_code, str)

        args = parse_argstring(self.dumbo, line)
        dumbo.run_cell(args.name, cell_code, self.shell.user_ns)


get_ipython().register_magics(DumboMagics)
