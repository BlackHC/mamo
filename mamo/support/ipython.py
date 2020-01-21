from IPython import get_ipython
from IPython.core.magic import Magics, magics_class, cell_magic
from IPython.core.magic_arguments import argument, magic_arguments, parse_argstring
import mamo


@magics_class
class MamoMagics(Magics):
    @cell_magic
    @magic_arguments()
    @argument("name", type=str, default=None, help="Name of the cell.")
    def mamo(self, line, cell_code):
        """mamo cell wrapper, only tracks global stores!"""
        assert isinstance(line, str)
        assert isinstance(cell_code, str)

        args = parse_argstring(self.mamo, line)
        mamo.run_cell(args.name, cell_code, self.shell.user_ns)


get_ipython().register_magics(MamoMagics)
