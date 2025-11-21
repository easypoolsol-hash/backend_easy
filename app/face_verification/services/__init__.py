"""
Face Verification Services - Single Responsibility Architecture

Each service has ONE responsibility:
- ConsensusService: Multi-model consensus verification
- ImageService: Image loading and conversion
- EmbeddingService: Student embedding management
- MultiCropService: Multi-crop voting strategy
"""

from .consensus_service import ConsensusResult, FaceVerificationConsensusService, ModelResult
from .embedding_service import EmbeddingService
from .image_service import ImageService
from .multi_crop_service import CropResult, MultiCropResult, MultiCropService

__all__ = [
    "ConsensusResult",
    "CropResult",
    "EmbeddingService",
    "FaceVerificationConsensusService",
    "ImageService",
    "ModelResult",
    "MultiCropResult",
    "MultiCropService",
]
