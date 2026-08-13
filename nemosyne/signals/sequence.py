from typing import Annotated

from blinker import Signal
from fastapi import Depends

from nemosyne.config.settings import get_settings

sequence_created = Signal()


def get_sequence_created_signal():
    return sequence_created


SequenceCreated = Annotated[Signal, Depends(get_sequence_created_signal)]


@sequence_created.connect
def handle_sequence_created(caller: str, session_id: str):
    settings = get_settings()
    print(caller, session_id)
    print(settings)
