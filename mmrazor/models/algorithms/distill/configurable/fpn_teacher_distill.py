# Copyright (c) OpenMMLab. All rights reserved.
from typing import List, Optional

import torch
from mmengine import BaseDataElement

from mmrazor.models.utils import add_prefix
from mmrazor.registry import MODELS
from ...base import LossResults
from .single_teacher_distill import SingleTeacherDistill


@MODELS.register_module()
class FpnTeacherDistill(SingleTeacherDistill):
    """``FpnTeacherDistill`` means teacher only execute backbone and neck.

    If the intermediate results required for distill algorithm are generated by
    the backbone and neck parts, using ``FpnTeacherDistill`` can speed up
    training.
    """

    def loss(
        self,
        batch_inputs: torch.Tensor,
        data_samples: Optional[List[BaseDataElement]] = None,
    ) -> LossResults:
        """Calculate losses from a batch of inputs and data samples."""

        losses = dict()
        # If the `override_data` of a delivery is False, the delivery will
        # record the origin data.
        self.delivery_manager.override_data = False
        if self.teacher_trainable:
            # Unlike ``SingleTeacherDistill``, teacher will only execute
            # back + neck, not head, so there will be no loss.
            with self.teacher_recorders, self.delivery_manager:
                _ = self.teacher.extract_feat(batch_inputs)
        else:
            with self.teacher_recorders, self.distill_deliveries:
                with torch.no_grad():
                    _ = self.teacher(batch_inputs, data_samples, mode='loss')

        # If the `override_data` of a delivery is True, the delivery will
        # override the origin data with the recorded data.
        self.delivery_manager.override_data = True
        with self.student_recorders, self.delivery_manager:
            student_losses = self.student(
                batch_inputs, data_samples, mode='loss')
        losses.update(add_prefix(student_losses, 'student'))

        # Automatically compute distill losses based on `loss_forward_mappings`
        distill_losses = self.compute_distill_losses(
            self.distill_losses, self.loss_forward_mappings,
            self.student_recorders, self.teacher_recorders)
        losses.update(add_prefix(distill_losses, 'distill'))

        return losses
