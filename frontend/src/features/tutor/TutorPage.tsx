import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { useConversations, useCreateConversation, useMessages, useSendMessage } from "../../api/tutor";
import type { TutorMessage } from "../../api/types";
import { EmptyState } from "../../components/shared/EmptyState";
import { ErrorState } from "../../components/shared/ErrorState";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Spinner } from "../../components/ui/Spinner";
import { Textarea } from "../../components/ui/Textarea";
import { useProjectId } from "../projects/useProjectId";
import { MessageBubble } from "./MessageBubble";

function pendingMessage(text: string): TutorMessage {
  return {
    id: "pending",
    conversation_id: "",
    role: "user",
    content: text,
    grounded: null,
    refusal_reason: "",
    citations: [],
    created_at: "",
  };
}

export function TutorPage() {
  const projectId = useProjectId();
  const conversations = useConversations(projectId);
  const createConversation = useCreateConversation(projectId);
  const sendMessage = useSendMessage(projectId);

  const [chosenId, setChosenId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [pendingText, setPendingText] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const conversationItems = conversations.data?.items ?? [];
  const selectedId = chosenId ?? conversationItems[0]?.id ?? null;
  const messages = useMessages(selectedId);
  const messageItems = messages.data?.items ?? [];
  const busy = sendMessage.isPending || createConversation.isPending;

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messageItems.length, pendingText]);

  function select(conversationId: string) {
    setChosenId(conversationId);
    sendMessage.reset();
  }

  async function submit(event?: FormEvent) {
    event?.preventDefault();
    const text = draft.trim();
    if (!text || busy) return;
    setPendingText(text);
    setDraft("");
    try {
      const conversationId = selectedId ?? (await createConversation.mutateAsync()).id;
      setChosenId(conversationId);
      await sendMessage.mutateAsync({ conversationId, text });
    } catch {
      // Nothing was saved on the server, so the learner gets their text back.
      setDraft(text);
    } finally {
      setPendingText(null);
    }
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void submit();
    }
  }

  if (conversations.isLoading) return <Spinner className="mx-auto mt-16" />;
  if (conversations.isError) return <ErrorState error={conversations.error} onRetry={() => conversations.refetch()} />;

  const error = sendMessage.error ?? createConversation.error;
  const showEmpty = !messages.isLoading && !messages.isError && messageItems.length === 0 && pendingText === null;

  return (
    <div className="grid gap-4 lg:grid-cols-[260px_1fr]">
      <Card
        title="Conversations"
        actions={
          <Button
            size="sm"
            variant="secondary"
            loading={createConversation.isPending}
            onClick={() => createConversation.mutate(undefined, { onSuccess: (created) => select(created.id) })}
          >
            New
          </Button>
        }
      >
        {conversationItems.length === 0 ? (
          <p className="text-sm text-slate-500">No conversations yet.</p>
        ) : (
          <ul className="space-y-1">
            {conversationItems.map((conversation) => (
              <li key={conversation.id}>
                <button
                  type="button"
                  onClick={() => select(conversation.id)}
                  aria-current={conversation.id === selectedId}
                  className={`w-full truncate rounded-md px-3 py-2 text-left text-sm ${
                    conversation.id === selectedId
                      ? "bg-indigo-50 font-medium text-indigo-800"
                      : "text-slate-700 hover:bg-slate-50"
                  }`}
                >
                  {conversation.title || "New conversation"}
                </button>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card className="flex min-h-[32rem] flex-col">
        <div className="flex-1 space-y-4 overflow-y-auto pb-4" aria-live="polite">
          {messages.isLoading && <Spinner className="mx-auto mt-8" />}
          {messages.isError && <ErrorState error={messages.error} onRetry={() => messages.refetch()} />}
          {showEmpty && (
            <EmptyState
              title="Ask your Tutor"
              description="Answers come from the materials in this project and link to the page they used. If your materials don't cover a question, the Tutor will say so."
            />
          )}
          {messageItems.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}
          {pendingText !== null && (
            <>
              <MessageBubble message={pendingMessage(pendingText)} pending />
              <p className="flex items-center gap-2 text-sm text-slate-500">
                <Spinner size="sm" />
                Reading your materials…
              </p>
            </>
          )}
          <div ref={bottomRef} />
        </div>

        {error && (
          <p role="alert" className="mb-2 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
            {error.message} Your question was not saved.
          </p>
        )}

        <form onSubmit={submit} className="flex items-end gap-2 border-t border-slate-100 pt-3">
          <div className="flex-1">
            <Textarea
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={onKeyDown}
              rows={2}
              maxLength={4000}
              disabled={busy}
              placeholder="Ask about your materials. Press Enter to send, Shift+Enter for a new line."
              aria-label="Your question"
            />
          </div>
          <Button type="submit" loading={busy} disabled={draft.trim().length === 0}>
            Send
          </Button>
        </form>
      </Card>
    </div>
  );
}
