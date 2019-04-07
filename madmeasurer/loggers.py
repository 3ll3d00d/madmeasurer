import logging
import sys

main_logger = logging.getLogger('verbose')
main_handler = logging.StreamHandler(sys.stdout)
main_formatter = logging.Formatter('%(asctime)s - %(message)s')
main_handler.setFormatter(main_formatter)
main_logger.addHandler(main_handler)

output_logger = logging.getLogger('output')
output_handler = logging.StreamHandler(sys.stdout)
output_formatter = logging.Formatter('%(message)s')
output_handler.setFormatter(output_formatter)
output_logger.addHandler(output_handler)

csv_logger = logging.getLogger('csv')

