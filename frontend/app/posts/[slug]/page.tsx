import { getPostBySlug, getPosts } from "@/lib/posts";
import Markdown from 'markdown-to-jsx';
import Link from "next/link";

export async function generateStaticParams() {
    const posts = getPosts();
    return posts.map((post) => ({
        slug: post.slug,
    }));
}

export default function PostPage({ params }: { params: { slug: string } }) {
    const post = getPostBySlug(params.slug);

    if (!post) {
        return <div>Post not found</div>;
    }

    return (
        <main className="min-h-screen bg-background text-foreground p-8 lg:p-24">
            <div className="max-w-3xl mx-auto">
                <Link href="/" className="text-sm text-gray-500 hover:text-white mb-8 block">
                    &larr; Back to Home
                </Link>

                <article className="prose prose-invert prose-lg max-w-none">
                    <h1 className="text-4xl lg:text-5xl font-bold mb-6 text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-purple-500">
                        {post.title}
                    </h1>
                    <div className="glass p-8 rounded-2xl mb-8">
                        <Markdown options={{
                            overrides: {
                                h1: { component: 'h2', props: { className: 'text-3xl font-bold mt-8 mb-4 text-blue-400' } },
                                h2: { component: 'h3', props: { className: 'text-2xl font-bold mt-6 mb-3 text-purple-400' } },
                                h3: { component: 'h4', props: { className: 'text-xl font-bold mt-4 mb-2' } },
                                p: { component: 'p', props: { className: 'mb-4 leading-relaxed text-gray-300' } },
                                ul: { component: 'ul', props: { className: 'list-disc pl-6 mb-4 space-y-2' } },
                                li: { component: 'li', props: { className: 'text-gray-300' } },
                                strong: { component: 'strong', props: { className: 'font-bold text-white' } },
                            }
                        }}>
                            {post.content}
                        </Markdown>
                    </div>
                </article>
            </div>
        </main>
    );
}
