"use client";

import classNames from "classnames";
import { useCallback, useEffect, useRef, useState } from "react";

import { LoadingIndicator } from "@/ui/App";
import { TextArea, Input } from "@/ui/elements";
import useChat from "@/modules/chat/hooks/useChat";

import styles from "./SearchView.module.css";

interface SelectOption {
  value: string;
  label: string;
}

interface SearchFormPayload extends HTMLFormElement {
  chatInput: HTMLInputElement;
}

const MAIN_DATASET = {
  id: "",
  data: [],
  status: "",
  name: "main_dataset",
};

export default function SearchView() {
  const searchOptions: SelectOption[] = [{
    value: "GRAPH_COMPLETION",
    label: "GraphRAG Completion",
  }, {
    value: "RAG_COMPLETION",
    label: "RAG Completion",
  }];

  const scrollToBottom = useCallback(() => {
    setTimeout(() => {
      const messagesContainerElement = document.getElementById("messages");
      if (messagesContainerElement) {
        const messagesElements = messagesContainerElement.children[0];

        if (messagesElements) {
          messagesContainerElement.scrollTo({
            top: messagesElements.scrollHeight,
            behavior: "smooth",
          });
        }
      }
    }, 300);
  }, []);

  // Hardcoded to `main_dataset` for now, change when multiple datasets are supported.
  const { messages, refreshChat, sendMessage, isSearchRunning } = useChat(MAIN_DATASET);

  useEffect(() => {
    refreshChat()
      .then(() => scrollToBottom());
  }, [refreshChat, scrollToBottom]);

  const [searchInputValue, setSearchInputValue] = useState("");
  // Add state for top_k
  const [topK, setTopK] = useState(10);

  const handleSearchInputChange = useCallback((value: string) => {
    setSearchInputValue(value);
  }, []);

  // Add handler for top_k input
  const handleTopKChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    let value = parseInt(e.target.value, 10);
    if (isNaN(value)) value = 10;
    if (value < 1) value = 1;
    if (value > 100) value = 100;
    setTopK(value);
  }, []);

  const handleChatMessageSubmit = useCallback((event: React.FormEvent<SearchFormPayload>) => {
    event.preventDefault();

    const formElements = event.currentTarget;
    const searchType = formElements.searchType.value;

    const chatInput = searchInputValue.trim();

    if (chatInput === "") {
      return;
    }

    scrollToBottom();

    setSearchInputValue("");
    
    // Pass topK to sendMessage
    sendMessage(chatInput, searchType, topK)
      .then(scrollToBottom)
  }, [scrollToBottom, sendMessage, searchInputValue, topK]);

  const chatFormRef = useRef<HTMLFormElement>(null);

  const handleSubmitOnEnter = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      chatFormRef.current?.requestSubmit();
    }
  };

  return (
    <div className="flex flex-col h-full bg-white rounded-2xl shadow-xl overflow-hidden">
      <form onSubmit={handleChatMessageSubmit} ref={chatFormRef} className="flex flex-col h-full">
        {/* Messages area */}
        <div className="flex-1 overflow-y-auto" id="messages">
          <div className="flex flex-col gap-3 items-end justify-end min-h-full px-6 py-4">
            {messages.map((message) => (
              <p
                key={message.id}
                className={classNames({
                  [classNames("ml-12 px-4 py-3 bg-indigo-50 text-gray-800 rounded-xl text-sm", styles.userMessage)]: message.user === "user",
                  [classNames("w-full px-4 py-3 text-gray-700 text-sm leading-relaxed", styles.systemMessage)]: message.user !== "user",
                })}
              >
                {message?.text && (
                  typeof(message.text) == "string" ? message.text : JSON.stringify(message.text)
                )}
              </p>
            ))}
          </div>
        </div>

        {/* Input area */}
        <div className="border-t border-gray-100 p-4 bg-gray-50 flex flex-col gap-3">
          <TextArea
            value={searchInputValue}
            onChange={handleSearchInputChange}
            onKeyUp={handleSubmitOnEnter}
            isAutoExpanding
            name="chatInput"
            placeholder="Ask anything"
            contentEditable={true}
            className="resize-none min-h-12 max-h-48 overflow-y-auto bg-white border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
          />
          <div className="flex flex-row items-center justify-between gap-4">
            <div className="flex flex-row items-center gap-4 flex-wrap">
              <div className="flex flex-row items-center gap-2">
                <label className="text-xs text-gray-500 whitespace-nowrap">Search type:</label>
                <div className="relative">
                  <select name="searchType" defaultValue={searchOptions[0].value} className="appearance-none pl-3 pr-8 h-8 text-xs rounded-lg border border-gray-200 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-300 cursor-pointer">
                    {searchOptions.map((option) => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                  </select>
                  <div className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-gray-400">
                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </div>
                </div>
              </div>
              <div className="flex flex-row items-center gap-2">
                <label className="text-xs text-gray-500 whitespace-nowrap">Max results:</label>
                <Input
                  type="number"
                  name="topK"
                  min={1}
                  max={100}
                  value={topK}
                  onChange={handleTopKChange}
                  className="w-16 text-xs px-2 py-1.5 rounded-lg border border-gray-200 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-300"
                  title="Controls how many results to return."
                />
              </div>
            </div>
            <button
              disabled={isSearchRunning}
              type="submit"
              className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-colors whitespace-nowrap"
            >
              {isSearchRunning && <LoadingIndicator />}
              {isSearchRunning ? "Searching..." : "Search"}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}