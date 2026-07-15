"""Progress reporting for the RAG pipeline's step stream.

The pipeline emits coarse-grained step start/end events through a
:class:`ProgressReporter`. A streaming endpoint can forward them to the client so
the UI can show which steps are currently in flight (a step is "in flight"
between its ``step_start`` and matching ``step_end``).
"""

import abc
import contextlib
import itertools
from typing import Iterator

import attrs
from anyio.streams import memory


@attrs.frozen
class StepStart:
    """A pipeline step has started."""

    id: str
    kind: str
    detail: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "type": "step_start",
            "id": self.id,
            "kind": self.kind,
            "detail": self.detail,
        }


@attrs.frozen
class StepEnd:
    """A previously started pipeline step has ended."""

    id: str

    def to_dict(self) -> dict[str, object]:
        return {"type": "step_end", "id": self.id}


@attrs.frozen
class AnswerChunk:
    """A fragment of the generated answer streamed as it is produced."""

    text: str

    def to_dict(self) -> dict[str, object]:
        return {"type": "answer_chunk", "text": self.text}


ProgressEvent = StepStart | StepEnd | AnswerChunk


class ProgressReporter(abc.ABC):
    """Sink for pipeline step events."""

    def __init__(self) -> None:
        self._counter = itertools.count()

    @abc.abstractmethod
    def _emit(self, event: ProgressEvent) -> None:
        """Deliver a single event to the sink."""

    @contextlib.contextmanager
    def step(self, kind: str, detail: str | None = None) -> Iterator[None]:
        """Emit a step-start on enter and the matching step-end on exit."""
        step_id = str(next(self._counter))
        self._emit(StepStart(id=step_id, kind=kind, detail=detail))
        try:
            yield
        finally:
            self._emit(StepEnd(id=step_id))

    def answer_chunk(self, text: str) -> None:
        """Emit a fragment of the generated answer as it streams in."""
        self._emit(AnswerChunk(text=text))


class _NullReporter(ProgressReporter):
    def _emit(self, event: ProgressEvent) -> None:
        pass


NULL_REPORTER: ProgressReporter = _NullReporter()


class StreamReporter(ProgressReporter):
    """Reporter that forwards events to an anyio memory object stream.

    Uses ``send_nowait`` so emitting never blocks the pipeline; the stream must
    therefore be created with an unbounded buffer.
    """

    def __init__(
        self, send_stream: memory.MemoryObjectSendStream[ProgressEvent]
    ) -> None:
        super().__init__()
        self._send_stream = send_stream

    def _emit(self, event: ProgressEvent) -> None:
        self._send_stream.send_nowait(event)
