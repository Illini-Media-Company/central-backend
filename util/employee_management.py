"""
This file defines the helper functions and error codes for the Employee Management System.

Created by Jacob Slabosz on Feb. 3, 2026
Last modified Feb. 3, 2026
"""

EUSERDNE = -1  # User does not exist
EEMPDNE = -2  # EmployeeCard does not exist
EPOSDNE = -3  # PositionCard does not exist
ERELDNE = -4  # EmployeePositionRelation does not exist

EMISSING = -5  # Required field is missing
EEXCEPT = -6  # Unknown exception occurred during operation
EEXISTS = -7  # EmployeeCard or EmployeePositionRelation already exists
ESUPREP = -8  # Error setting supervisor(s) or direct report(s)
EGROUP = -9  # Google Groups update failed
EGROUPDNE = -10  # Google Group email does not exist or is invalid
ESLACKDNE = -11  # Slack channel ID does not exist or is not accessible


# Get correct image URL
def get_ems_brand_image_url(brand: str) -> str:
    """
    Returns the image URL for a given brand.

    Args:
        brand (str): The brand name.

    Returns:
        str: The image URL for the brand.
    """
    brand_images = {
        "Chambana Eats": "/static/brandmarks/background/96x96/CE_SquareIcon.png",
        "The Daily Illini": "/static/brandmarks/background/96x96/DI_SquareIcon.png",
        "Illini Content Studio": "/static/brandmarks/background/96x96/ICS_SquareIcon.png",
        "Illio": "/static/brandmarks/background/96x96/Illio_SquareIcon.png",
        "IMC": "/static/brandmarks/background/96x96/IMC_SquareIcon.png",
        "WPGU": "/static/brandmarks/background/96x96/WPGU_SquareIcon.png",
    }
    return brand_images.get(brand, "/static/defaults/position_profile.png")
