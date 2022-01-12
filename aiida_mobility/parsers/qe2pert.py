from aiida import orm
from aiida.common.exceptions import NotExistent
from aiida.parsers.parser import Parser
from aiida.engine import ExitCode
import os
import re
from aiida_mobility.calculations.qe2pert import QE2PertCalculation


class QE2PertParser(Parser):
    """Parser for an `QE2PertCalculation` job."""

    def parse(self, **kwargs):
        """Parse the contents of the output files stored in the `retrieved` output node."""

        try:
            retrieved = self.retrieved
        except NotExistent:
            self.logger.error("No retrieved folder found")
            return self.exit_codes.ERROR_NO_RETRIEVED_FOLDER

        # The stdout is required for parsing
        filename_stdout = self.node.get_attribute("output_filename")

        if filename_stdout not in retrieved.list_object_names():
            return self.exit_codes.ERROR_OUTPUT_STDOUT_MISSING

        try:
            stdout = retrieved.get_object_content(filename_stdout)

            progress = re.search("progress:\W+100\.00\%", stdout)
            if progress is None:
                # failed
                self.logger.error("ERROR_OUTPUT_STDOUT_INCOMPLETE")

                # parse carsh info
                crash_info = re.search(
                    "(?<=\%\n).+(?=\n.+\%)", stdout, re.M | re.S
                ).group()
                self.logger.error(crash_info)

                return self.exit_codes.ERROR_OUTPUT_STDOUT_INCOMPLETE
            else:
                # finished
                cpu_time = re.search(
                    "([\d\.]+h)?([\d\.]+m)?([\d\.]+s)?(?=\W+CPU)", stdout
                ).group()
                wall_time = re.search(
                    "([\d\.]+h)?([\d\.]+m)?([\d\.]+s)?(?=\W+WALL)", stdout
                ).group()
                self.out(
                    "output_parameters",
                    orm.Ditc(
                        dict={
                            "cpu_time": cpu_time,
                            "wall_time": wall_time,
                        }
                    ),
                )

                retrieve_temporary_list = self.node.get_attribute(
                    "retrieve_temporary_list", None
                )
                if retrieve_temporary_list:
                    retrieved_temporary_folder = kwargs.get(
                        "retrieved_temporary_folder", None
                    )
                    if retrieved_temporary_folder is None:
                        self.logger.warning(
                            "ERROR_NO_RETRIEVED_TEMPORARY_FOLDER. [This will be an error in future versions.]"
                        )
                        # return self.exit_codes.ERROR_NO_RETRIEVED_TEMPORARY_FOLDER
                    # # epwan.hdf5
                    # filename = os.path.join(
                    #     retrieved_temporary_folder,
                    #     QE2PertCalculation._DEFAULT_EPWAN_FILE,
                    # )
        except (IOError, OSError):
            return self.exit_codes.ERROR_OUTPUT_STDOUT_READ
        return ExitCode(0)

    def read_epwan(self, filename):
        """read_epwan Read epwan data from an HDF5 file .

        Args:
            filename ([type]): [h5 file path]

        TODO: read ep_hop data to generate figures [arXiv:2105.04192v1: First-principles predictions of Hall and drift mobilities in semiconductors]
        """
        import h5py

        h5 = h5py.File(filename)
        na = h5["basic_data"]["nat"][()]
        nb = h5["basic_data"]["num_wann"][()]
        eph_matrix_wannier = h5["eph_matrix_wannier"]
        ni, nj, _ = eph_matrix_wannier["ep_hop_r_1_1_1"].shape
        for ri in range(0, ni):
            for rj in range(0, nj):
                max_cur = 0
                for ia in range(1, na + 1):
                    for jw in range(1, nb + 1):
                        for iw in range(1, nb + 1):
                            try:
                                ep_hop = eph_matrix_wannier[
                                    f"ep_hop_r_{ia}_{jw}_{iw}"
                                ]
                                temp = max(abs(ep_hop[ri, rj, :]))
                            except Exception:
                                continue
                            if max_cur < temp:
                                max_cur = temp
