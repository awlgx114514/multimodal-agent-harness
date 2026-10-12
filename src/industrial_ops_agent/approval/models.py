"""Approval invariant errors retained for generic governance utilities."""


class ApprovalNotVisible(Exception):
    pass


class ApprovalConflict(Exception):
    pass


class SeparationOfDutiesViolation(Exception):
    pass
