"use client";
import { useEffect, useState, useRef, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';

// --- Metadata dos agentes para exibição ---
const AGENT_INFO: Record<string, { label: string; emoji: string; color: string; bgColor: string; borderColor: string }> = {
    ceo: {
        label: "CEO",
        emoji: "👔",
        color: "text-indigo-700",
        bgColor: "bg-indigo-50",
        borderColor: "border-indigo-200",
    },
    portfolio_manager: {
        label: "Gestor de Portfólio",
        emoji: "💼",
        color: "text-blue-700",
        bgColor: "bg-blue-50",
        borderColor: "border-blue-200",
    },
    product_manager: {
        label: "Gestor de Produto",
        emoji: "📝",
        color: "text-emerald-700",
        bgColor: "bg-emerald-50",
        borderColor: "border-emerald-200",
    },
    critic: {
        label: "Crítico de Qualidade",
        emoji: "🧐",
        color: "text-amber-700",
        bgColor: "bg-amber-50",
        borderColor: "border-amber-200",
    },
    writer: {
        label: "Redator",
        emoji: "✍️",
        color: "text-purple-700",
        bgColor: "bg-purple-50",
        borderColor: "border-purple-200",
    },
    human: {
        label: "Você",
        emoji: "👤",
        color: "text-sky-700",
        bgColor: "bg-sky-50",
        borderColor: "border-sky-200",
    },
};

const DEFAULT_AGENT = {
    label: "Sistema",
    emoji: "⚙️",
    color: "text-gray-700",
    bgColor: "bg-gray-50",
    borderColor: "border-gray-200",
};

function getAgentInfo(name: string) {
    return AGENT_INFO[name] || DEFAULT_AGENT;
}

// --- Labels de status ---
const STATUS_LABELS: Record<string, { label: string; color: string }> = {
    IDLE: { label: "Aguardando", color: "bg-gray-400" },
    PROCESSING: { label: "Processando...", color: "bg-green-500 animate-pulse" },
    WAITING_FOR_APPROVAL: { label: "Aguardando Aprovação", color: "bg-yellow-500 animate-pulse" },
    error: { label: "Erro", color: "bg-red-500" },
};

// --- Pipeline step type ---
type PipelineStep = { id: string; label: string; emoji: string };
type PipelineData = {
    is_running: boolean;
    current_step: string | null;
    steps_completed: string[];
    steps: PipelineStep[];
    elapsed_seconds: number | null;
    error: string | null;
};

function formatElapsed(seconds: number | null): string {
    if (!seconds) return "0s";
    if (seconds < 60) return `${Math.round(seconds)}s`;
    const mins = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    return `${mins}m ${secs}s`;
}

export default function Dashboard() {
    const [logs, setLogs] = useState<any[]>([]);
    const [status, setStatus] = useState("IDLE");
    const [topic, setTopic] = useState("");
    const [plan, setPlan] = useState<any>(null);
    const [comment, setComment] = useState("");
    const [memory, setMemory] = useState("");
    const [posts, setPosts] = useState<any[]>([]);
    const [serverLogs, setServerLogs] = useState<string[]>([]);
    const [recommendations, setRecommendations] = useState<any[]>([]);
    const [isAnalyzing, setIsAnalyzing] = useState(false);
    const [isStarting, setIsStarting] = useState(false);
    const [pipeline, setPipeline] = useState<PipelineData | null>(null);
    const logsEndRef = useRef<HTMLDivElement>(null);
    const serverLogsEndRef = useRef<HTMLDivElement>(null);

    const fetchStatus = useCallback(async () => {
        try {
            const res = await fetch('/api/agent/status');
            const data = await res.json();
            setLogs(data.messages || []);
            setStatus(data.status);
            setPlan(data.plan);
            if (data.status !== "PROCESSING") {
                setIsStarting(false);
            }
        } catch (e) {
            console.error("Erro ao buscar status", e);
        }
    }, []);

    const fetchPipeline = useCallback(async () => {
        try {
            const res = await fetch('/api/agent/pipeline');
            const data = await res.json();
            setPipeline(data);
            if (!data.is_running) {
                setIsStarting(false);
            }
        } catch (e) {
            // silent — pipeline endpoint may not exist yet
        }
    }, []);

    const fetchExtras = useCallback(async () => {
        try {
            const [memRes, postsRes, logsRes] = await Promise.all([
                fetch('/api/agent/memory'),
                fetch('/api/agent/posts'),
                fetch('/api/agent/logs'),
            ]);
            const memData = await memRes.json();
            const postsData = await postsRes.json();
            const logsData = await logsRes.json();

            setMemory(memData.memory);
            setPosts(postsData.posts);
            setServerLogs(logsData.logs || []);
        } catch (e) {
            console.error("Erro ao buscar dados extras", e);
        }
    }, []);

    // Fast polling when active (1s), slow when idle (4s)
    useEffect(() => {
        const isActive = status === "PROCESSING" || isStarting;
        const interval = setInterval(() => {
            fetchStatus();
            fetchPipeline();
            fetchExtras();
        }, isActive ? 1000 : 4000);

        return () => clearInterval(interval);
    }, [status, isStarting, fetchStatus, fetchPipeline, fetchExtras]);

    useEffect(() => {
        logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [logs.length]);

    useEffect(() => {
        serverLogsEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [serverLogs.length]);

    const startAgent = async () => {
        if (!topic || isStarting) return;
        setIsStarting(true);
        setStatus("PROCESSING");
        setPipeline(null);  // Reset pipeline display
        try {
            await fetch('/api/agent/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ topic }),
            });
        } catch (e) {
            console.error("Erro ao iniciar agente", e);
            setIsStarting(false);
        }
        setTopic("");
        // Immediately fetch pipeline status
        fetchPipeline();
        fetchStatus();
    };

    const runAnalysis = async () => {
        setIsAnalyzing(true);
        try {
            const res = await fetch('/api/agent/analyze', { method: 'POST' });
            const data = await res.json();
            setRecommendations(data.recommendations || []);
        } catch (e) {
            console.error("Análise falhou", e);
        }
        setIsAnalyzing(false);
    };

    const sendFeedback = async (approved: boolean) => {
        await fetch('/api/agent/feedback', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ approved, comments: comment }),
        });
        setComment("");
    };

    const statusInfo = STATUS_LABELS[status] || STATUS_LABELS.IDLE;

    return (
        <main className="min-h-screen bg-gray-50 text-gray-900 p-8 font-sans">
            <header className="mb-8 flex justify-between items-center border-b border-gray-200 pb-4">
                <h1 className="text-3xl font-bold text-blue-600">🤖 Central de Comando</h1>
                <div className="flex items-center gap-2 bg-white px-3 py-1 rounded-full border border-gray-300 shadow-sm">
                    <span className={`w-3 h-3 rounded-full ${statusInfo.color}`}></span>
                    <span className="text-sm font-mono text-gray-600">{statusInfo.label}</span>
                </div>
            </header>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 h-[calc(100vh-140px)]">
                {/* Área principal (Chat + Terminal) */}
                <div className="lg:col-span-2 flex flex-col gap-6 h-full">

                    {/* Pipeline Progress — only visible when running */}
                    {(status === "PROCESSING" || isStarting) && pipeline?.steps && (
                        <div className="border border-blue-200 rounded-xl p-5 bg-white shadow-sm shrink-0">
                            <div className="flex items-center justify-between mb-3">
                                <h2 className="text-sm font-semibold text-blue-700 flex items-center gap-2">
                                    <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse"></span>
                                    Pipeline em execução
                                </h2>
                                <span className="text-xs text-gray-500 font-mono">
                                    ⏱ {formatElapsed(pipeline.elapsed_seconds)}
                                </span>
                            </div>

                            {/* Step indicators */}
                            <div className="flex items-center gap-1">
                                {pipeline.steps.map((step, i) => {
                                    const isCompleted = pipeline.steps_completed.includes(step.id);
                                    const isCurrent = pipeline.current_step === step.id;
                                    const isPending = !isCompleted && !isCurrent;

                                    return (
                                        <div key={step.id} className="flex items-center flex-1 min-w-0">
                                            <div className="flex flex-col items-center flex-1 min-w-0">
                                                {/* Step circle */}
                                                <div className={`
                                                    w-8 h-8 rounded-full flex items-center justify-center text-sm
                                                    transition-all duration-500
                                                    ${isCompleted ? 'bg-green-100 border-2 border-green-400' : ''}
                                                    ${isCurrent ? 'bg-blue-100 border-2 border-blue-500 animate-pulse ring-4 ring-blue-100' : ''}
                                                    ${isPending ? 'bg-gray-100 border-2 border-gray-200' : ''}
                                                `}>
                                                    {isCompleted ? '✅' : step.emoji}
                                                </div>
                                                {/* Step label */}
                                                <span className={`
                                                    text-[10px] mt-1 text-center leading-tight truncate w-full px-1
                                                    ${isCurrent ? 'text-blue-700 font-semibold' : ''}
                                                    ${isCompleted ? 'text-green-600' : ''}
                                                    ${isPending ? 'text-gray-400' : ''}
                                                `}>
                                                    {step.label.split(' ').slice(0, 2).join(' ')}
                                                </span>
                                            </div>
                                            {/* Connector line */}
                                            {i < pipeline.steps.length - 1 && (
                                                <div className={`
                                                    h-0.5 w-4 shrink-0 mx-0.5 mt-[-12px]
                                                    ${isCompleted ? 'bg-green-300' : 'bg-gray-200'}
                                                `}></div>
                                            )}
                                        </div>
                                    );
                                })}
                            </div>

                            {/* Current action description */}
                            {pipeline.current_step && (
                                <div className="mt-3 pt-3 border-t border-blue-100">
                                    <p className="text-xs text-blue-600 flex items-center gap-2">
                                        <span className="inline-block w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse"></span>
                                        {pipeline.steps.find(s => s.id === pipeline.current_step)?.emoji}{' '}
                                        {pipeline.steps.find(s => s.id === pipeline.current_step)?.label}...
                                    </p>
                                </div>
                            )}

                            {/* Error display */}
                            {pipeline.error && (
                                <div className="mt-3 pt-3 border-t border-red-200">
                                    <p className="text-xs text-red-600">❌ Erro: {pipeline.error}</p>
                                </div>
                            )}
                        </div>
                    )}
                    {/* Conversa dos Agentes */}
                    <div className="flex-1 border border-gray-200 rounded-xl p-6 bg-white flex flex-col shadow-sm min-h-0">
                        <h2 className="text-xl font-semibold mb-4 border-b border-gray-100 pb-2 text-gray-800">
                            Conversa dos Agentes
                        </h2>
                        <div className="flex-1 overflow-y-auto space-y-4 pr-2 scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-transparent">
                            {logs.length === 0 && (
                                <div className="flex items-center justify-center h-full text-gray-400 italic">
                                    Nenhuma mensagem ainda. Inicie uma nova missão.
                                </div>
                            )}
                            {logs.map((msg, i) => {
                                const agent = getAgentInfo(msg.name || msg.role);
                                const isHuman = msg.role === 'human';
                                return (
                                    <div
                                        key={i}
                                        className={`rounded-lg border ${agent.borderColor} ${agent.bgColor} overflow-hidden`}
                                    >
                                        {/* Cabeçalho do agente */}
                                        <div className={`px-4 py-2 border-b ${agent.borderColor} flex items-center gap-2`}>
                                            <span className="text-lg">{agent.emoji}</span>
                                            <span className={`text-sm font-semibold ${agent.color}`}>
                                                {agent.label}
                                            </span>
                                            {isHuman && (
                                                <span className="ml-auto text-xs bg-sky-100 text-sky-600 px-2 py-0.5 rounded-full">
                                                    Revisão Humana
                                                </span>
                                            )}
                                        </div>
                                        {/* Conteúdo da mensagem */}
                                        <div className="px-4 py-3">
                                            <div className="prose prose-sm max-w-none text-gray-800 break-words overflow-x-auto
                                                prose-strong:text-gray-900
                                                prose-blockquote:border-l-4 prose-blockquote:border-gray-300 prose-blockquote:pl-4 prose-blockquote:text-gray-600
                                                prose-li:text-gray-700
                                                prose-p:leading-relaxed">
                                                <ReactMarkdown>{msg.content}</ReactMarkdown>
                                            </div>
                                        </div>
                                    </div>
                                );
                            })}
                            <div ref={logsEndRef} />
                        </div>
                    </div>

                    {/* Terminal do Backend */}
                    <div className="border border-gray-200 rounded-xl p-6 bg-gray-900 text-green-400 flex flex-col shadow-sm font-mono text-xs h-48 shrink-0">
                        <h2 className="text-sm font-bold mb-2 text-gray-400 border-b border-gray-700 pb-1">Terminal do Backend</h2>
                        <div className="flex-1 overflow-y-auto space-y-1">
                            {serverLogs.map((log, i) => (
                                <div key={i} className="break-words">
                                    <span className="text-gray-500 mr-2">{log.split(' - ')[0]}</span>
                                    <span>{log.split(' - ').slice(1).join(' - ')}</span>
                                </div>
                            ))}
                            <div ref={serverLogsEndRef} />
                        </div>
                    </div>
                </div>

                {/* Controles laterais */}
                <div className="space-y-6 h-full overflow-y-auto pr-2">
                    {/* Nova Missão */}
                    <div className="border border-gray-200 rounded-xl p-6 bg-white shadow-sm">
                        <h2 className="text-xl font-semibold mb-4 text-gray-800">Nova Missão</h2>
                        <div className="flex gap-2">
                            <input
                                type="text"
                                value={topic}
                                onChange={(e) => setTopic(e.target.value)}
                                onKeyDown={(e) => e.key === 'Enter' && startAgent()}
                                placeholder="Ex: Melhores mouses gamer 2026"
                                disabled={isStarting}
                                className="flex-1 bg-white border border-gray-300 rounded px-3 py-2 text-gray-900 focus:outline-none focus:border-blue-500 placeholder-gray-400 disabled:opacity-50"
                            />
                            <button
                                onClick={startAgent}
                                disabled={isStarting || !topic}
                                className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded font-medium transition-colors shadow-sm disabled:opacity-50 disabled:cursor-not-allowed min-w-[90px]"
                            >
                                {isStarting ? (
                                    <span className="flex items-center gap-2">
                                        <span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
                                        <span>...</span>
                                    </span>
                                ) : 'Iniciar'}
                            </button>
                        </div>
                    </div>

                    {/* Insights do Analista */}
                    <div className="border border-purple-200 rounded-xl p-6 bg-purple-50 shadow-sm">
                        <div className="flex justify-between items-center mb-4">
                            <h2 className="text-xl font-semibold text-purple-800">🔮 Insights do Analista</h2>
                            <button
                                onClick={runAnalysis}
                                disabled={isAnalyzing}
                                className="text-xs bg-purple-600 text-white px-3 py-1 rounded hover:bg-purple-700 disabled:opacity-50 transition-colors"
                            >
                                {isAnalyzing ? 'Analisando...' : 'Analisar'}
                            </button>
                        </div>

                        {recommendations.length > 0 ? (
                            <div className="space-y-3">
                                {recommendations.map((rec, i) => (
                                    <div key={i} className="bg-white p-3 rounded border border-purple-100 hover:border-purple-300 cursor-pointer transition-colors group" onClick={() => setTopic(rec.topic)}>
                                        <div className="flex justify-between items-start">
                                            <h3 className="font-medium text-purple-900 group-hover:text-purple-700">{rec.topic}</h3>
                                            <span className="text-xs text-purple-400 opacity-0 group-hover:opacity-100 transition-opacity">Clique para usar</span>
                                        </div>
                                        <p className="text-xs text-purple-600 mt-1">{rec.reason}</p>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <p className="text-sm text-purple-400 italic">Execute a análise para encontrar lacunas de conteúdo.</p>
                        )}
                    </div>

                    {/* Painel de Aprovação */}
                    {status === 'WAITING_FOR_APPROVAL' && plan && (
                        <div className="border border-yellow-200 rounded-xl p-6 bg-yellow-50 animate-in fade-in slide-in-from-bottom-4 shadow-sm">
                            <h2 className="text-xl font-semibold mb-4 text-yellow-700">⚠️ Aprovação Necessária</h2>

                            <div className="bg-white p-4 rounded mb-4 text-sm border border-gray-200 text-gray-700 space-y-1">
                                <p><strong className="text-gray-900">Tópico:</strong> {plan.topic}</p>
                                <p><strong className="text-gray-900">Ângulo:</strong> {plan.angle}</p>
                                <p><strong className="text-gray-900">Público:</strong> {plan.target_audience || 'N/A'}</p>
                                <p><strong className="text-gray-900">Produtos:</strong> {plan.key_products?.join(', ') || 'Nenhum'}</p>
                            </div>

                            <div className="space-y-3">
                                <textarea
                                    value={comment}
                                    onChange={(e) => setComment(e.target.value)}
                                    placeholder="Comentários (caso rejeite)..."
                                    className="w-full bg-white border border-gray-300 rounded px-3 py-2 text-gray-900 text-sm focus:outline-none focus:border-yellow-500 placeholder-gray-400"
                                    rows={3}
                                />
                                <div className="flex gap-2">
                                    <button
                                        onClick={() => sendFeedback(false)}
                                        className="flex-1 bg-red-100 hover:bg-red-200 text-red-700 border border-red-200 px-4 py-2 rounded font-medium transition-colors"
                                    >
                                        Rejeitar
                                    </button>
                                    <button
                                        onClick={() => sendFeedback(true)}
                                        className="flex-1 bg-green-100 hover:bg-green-200 text-green-700 border border-green-200 px-4 py-2 rounded font-medium transition-colors"
                                    >
                                        Aprovar
                                    </button>
                                </div>
                            </div>
                        </div>
                    )}

                    {status === 'IDLE' && (
                        <div className="text-center text-gray-400 mt-10 p-4 border border-dashed border-gray-200 rounded-lg">
                            <p>Sistema pronto. Aguardando entrada.</p>
                        </div>
                    )}

                    {/* Banco de Memória */}
                    <div className="border border-gray-200 rounded-xl p-6 bg-white shadow-sm">
                        <h2 className="text-xl font-semibold mb-4 text-gray-800">🧠 Banco de Memória</h2>
                        <div className="bg-gray-50 p-4 rounded border border-gray-100 text-sm text-gray-600 max-h-40 overflow-y-auto">
                            {memory ? (
                                <p className="whitespace-pre-wrap">{memory}</p>
                            ) : (
                                <p className="italic">Nenhuma memória registrada ainda.</p>
                            )}
                        </div>
                    </div>

                    {/* Rascunhos Recentes */}
                    <div className="border border-gray-200 rounded-xl p-6 bg-white shadow-sm">
                        <h2 className="text-xl font-semibold mb-4 text-gray-800">📄 Rascunhos Recentes</h2>
                        <div className="space-y-2">
                            {posts.length > 0 ? posts.slice(-3).reverse().map((post, i) => (
                                <div key={i} className="p-3 bg-gray-50 rounded border border-gray-100">
                                    <p className="font-medium text-gray-900 truncate">{post.title}</p>
                                    <p className="text-xs text-gray-500">{post.slug}</p>
                                </div>
                            )) : (
                                <p className="text-sm text-gray-500 italic">Nenhum rascunho criado ainda.</p>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </main>
    );
}
