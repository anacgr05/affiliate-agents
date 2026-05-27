"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";

type AffiliateLink = {
  store?: string;
  url?: string;
  price?: string;
};

type Product = {
  name?: string;
  price?: string;
  rating?: number | string | null;
  pros?: unknown;
  cons?: unknown;
  verdict?: string;
  affiliate_links?: unknown;
};

type BuyingStep = {
  title?: string;
  content?: string;
};

type FaqItem = {
  question?: string;
  answer?: string;
};

type Post = {
  slug?: string;
  title?: string;
  excerpt?: string;
  image_url?: string | null;
  image_status?: string | null;
  hero?: {
    title?: string;
    subtitle?: string;
    image_prompt?: string;
    image?: string;
  };
  products?: unknown;
  buying_guide?: {
    title?: string;
    steps?: unknown;
  };
  faq?: unknown;
};

function asText(value: unknown, fallback = ""): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return fallback;
}

function asArray<T = unknown>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

function asNumber(value: unknown, fallback = 0): number {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const normalized = value.replace(",", ".").replace(/[^\d.]/g, "");
    const n = Number(normalized);
    if (Number.isFinite(n)) return n;
  }
  return fallback;
}

function normalizeImageUrl(url?: string | null): string | null {
  if (!url) return null;
  if (url.startsWith("http://") || url.startsWith("https://")) return url;

  // Se o backend devolver "/images/arquivo.png", a Vercel precisa apontar
  // para o backend do Render, não para o domínio da Vercel.
  const apiBase = process.env.NEXT_PUBLIC_API_URL ?? process.env.NEXT_PUBLIC_BACKEND_URL ?? "";
  if (url.startsWith("/") && apiBase) {
    return `${apiBase.replace(/\/$/, "")}${url}`;
  }

  return url;
}

function StarRating({ rating }: { rating: unknown }) {
  const safeRating = asNumber(rating, 0);
  const rounded = Math.max(0, Math.min(5, Math.round(safeRating)));

  return (
    <div className="flex items-center gap-1">
      {[1, 2, 3, 4, 5].map((star) => (
        <svg
          key={star}
          className={`w-4 h-4 ${star <= rounded ? "text-yellow-400" : "text-gray-200"}`}
          fill="currentColor"
          viewBox="0 0 20 20"
        >
          <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
        </svg>
      ))}
      <span className="text-sm text-gray-500 ml-1">
        {safeRating > 0 ? safeRating.toFixed(1) : "N/A"}
      </span>
    </div>
  );
}

export default function ReviewPage() {
  const params = useParams();
  const slug = asText(params?.slug);

  const [post, setPost] = useState<Post | null>(null);
  const [coverUrl, setCoverUrl] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [openFaq, setOpenFaq] = useState<number | null>(null);

  useEffect(() => {
    if (!slug) {
      setNotFound(true);
      return;
    }

    let mounted = true;

    fetch("/api/agent/posts")
      .then((r) => r.json())
      .then((data) => {
        if (!mounted) return;

        const posts = Array.isArray(data?.posts) ? data.posts : [];
        const found = posts.find((p: Post) => p?.slug === slug) ?? null;

        if (found) {
          setPost(found);

          const image =
            found.image_status === "ready" && found.image_url
              ? found.image_url
              : found.hero?.image ?? null;

          setCoverUrl(normalizeImageUrl(image));
        } else {
          setNotFound(true);
        }
      })
      .catch((err) => {
        console.error("Erro ao carregar post:", err);
        if (mounted) setNotFound(true);
      });

    // Usa o proxy da Vercel. Não chama o Render direto pelo navegador.
    // Se o stream falhar, a página continua funcionando.
    let source: EventSource | null = null;
    try {
      source = new EventSource(`/api/agent/posts/stream?slug=${encodeURIComponent(slug)}`);
      source.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);
          if (data.type === "image_ready") {
            setCoverUrl(normalizeImageUrl(data.url));
            source?.close();
          } else if (data.type === "image_failed") {
            source?.close();
          }
        } catch (err) {
          console.warn("Evento de imagem ignorado:", err);
        }
      };
      source.onerror = () => {
        source?.close();
      };
    } catch (err) {
      console.warn("Stream de imagem indisponível:", err);
    }

    return () => {
      mounted = false;
      source?.close();
    };
  }, [slug]);

  const products = useMemo(() => asArray<Product>(post?.products), [post]);
  const buyingSteps = useMemo(() => asArray<BuyingStep>(post?.buying_guide?.steps), [post]);
  const faq = useMemo(() => asArray<FaqItem>(post?.faq), [post]);

  if (notFound) {
    return <p className="p-8 text-gray-500">Post não encontrado.</p>;
  }

  if (!post) {
    return (
      <div className="max-w-4xl mx-auto p-6 animate-pulse space-y-4">
        <div className="h-64 bg-gray-200 rounded-xl" />
        <div className="h-8 bg-gray-200 rounded w-3/4" />
        <div className="h-4 bg-gray-200 rounded w-full" />
        <div className="h-4 bg-gray-200 rounded w-5/6" />
      </div>
    );
  }

  const title = post.hero?.title || post.title || "Review";
  const subtitle = post.hero?.subtitle;
  const excerpt = post.excerpt || "Análise completa do produto.";

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 space-y-12">
      {/* Hero */}
      <section>
        <div className="w-full h-72 bg-gray-100 rounded-2xl overflow-hidden mb-6 relative">
          {coverUrl && !coverUrl.includes("placehold.co") ? (
            <img src={coverUrl} alt={title} className="object-cover w-full h-full" />
          ) : (
            <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100">
              <p className="text-gray-400 text-sm">Imagem do artigo em processamento...</p>
            </div>
          )}
        </div>

        <h1 className="text-4xl font-bold text-gray-900 mb-3 leading-tight">
          {title}
        </h1>

        {subtitle && <p className="text-xl text-gray-500 mb-4">{subtitle}</p>}

        <p className="text-gray-600 text-lg">{excerpt}</p>
      </section>

      {/* Produtos */}
      {products.length > 0 && (
        <section className="space-y-6">
          <h2 className="text-2xl font-bold text-gray-900 border-b border-gray-200 pb-3">
            Produtos em Destaque
          </h2>

          {products.map((product, i) => {
            const pros = asArray<string>(product.pros);
            const cons = asArray<string>(product.cons);
            const links = asArray<AffiliateLink>(product.affiliate_links);

            return (
              <div key={i} className="border border-gray-200 rounded-xl p-6 hover:shadow-md transition-shadow">
                <div className="flex flex-wrap justify-between items-start gap-2 mb-3">
                  <div>
                    <h3 className="text-xl font-bold text-gray-900">
                      {asText(product.name, `Produto ${i + 1}`)}
                    </h3>
                    <StarRating rating={product.rating} />
                  </div>
                  <span className="text-2xl font-bold text-green-700">
                    {asText(product.price, "Preço sob consulta")}
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4 text-sm">
                  <div className="bg-green-50 rounded-lg p-3">
                    <p className="font-semibold text-green-800 mb-2">Prós</p>
                    {pros.length > 0 ? (
                      <ul className="space-y-1">
                        {pros.map((pro, j) => (
                          <li key={j} className="text-green-700 flex gap-2">
                            <span className="shrink-0">✓</span>
                            {asText(pro)}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-green-700">Informação não disponível.</p>
                    )}
                  </div>

                  <div className="bg-red-50 rounded-lg p-3">
                    <p className="font-semibold text-red-800 mb-2">Contras</p>
                    {cons.length > 0 ? (
                      <ul className="space-y-1">
                        {cons.map((con, j) => (
                          <li key={j} className="text-red-700 flex gap-2">
                            <span className="shrink-0">✗</span>
                            {asText(con)}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-red-700">Nenhum contra relevante informado.</p>
                    )}
                  </div>
                </div>

                <p className="text-gray-600 text-sm italic mb-4 border-l-4 border-blue-200 pl-3">
                  {asText(product.verdict, "Produto recomendado conforme o perfil do consumidor.")}
                </p>

                {links.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {links.map((link, j) => {
                      const href = asText(link.url, "#");
                      return (
                        <a
                          key={j}
                          href={href}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-2 bg-blue-600 text-white px-5 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
                        >
                          {asText(link.store, "Loja")} — {asText(link.price, "Ver preço")}
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                          </svg>
                        </a>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </section>
      )}

      {/* Guia de Compra */}
      {buyingSteps.length > 0 && (
        <section className="space-y-4">
          <h2 className="text-2xl font-bold text-gray-900 border-b border-gray-200 pb-3">
            {post.buying_guide?.title ?? "Guia de Compra"}
          </h2>

          <div className="space-y-4">
            {buyingSteps.map((step, i) => (
              <div key={i} className="flex gap-4">
                <div className="shrink-0 w-8 h-8 rounded-full bg-blue-600 text-white flex items-center justify-center font-bold text-sm">
                  {i + 1}
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900 mb-1">
                    {asText(step.title, `Passo ${i + 1}`)}
                  </h3>
                  <p className="text-gray-600 text-sm leading-relaxed">
                    {asText(step.content, "Sem descrição disponível.")}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* FAQ */}
      {faq.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-2xl font-bold text-gray-900 border-b border-gray-200 pb-3">
            Perguntas Frequentes
          </h2>

          {faq.map((item, i) => (
            <div key={i} className="border border-gray-200 rounded-xl overflow-hidden">
              <button
                className="w-full text-left px-5 py-4 font-semibold text-gray-900 hover:bg-gray-50 flex justify-between items-center gap-4"
                onClick={() => setOpenFaq(openFaq === i ? null : i)}
              >
                <span>{asText(item.question, `Pergunta ${i + 1}`)}</span>
                <svg
                  className={`w-5 h-5 text-gray-400 shrink-0 transition-transform ${openFaq === i ? "rotate-180" : ""}`}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>

              {openFaq === i && (
                <div className="px-5 pb-4 text-gray-600 text-sm leading-relaxed border-t border-gray-100 pt-3">
                  {asText(item.answer, "Resposta não disponível.")}
                </div>
              )}
            </div>
          ))}
        </section>
      )}
    </div>
  );
}
