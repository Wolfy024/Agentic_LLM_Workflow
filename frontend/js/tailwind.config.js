tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          colors: {
            border: 'hsl(240 3.7% 15.9%)',
            input: 'hsl(240 3.7% 15.9%)',
            ring: 'hsl(240 4.9% 83.9%)',
            background: 'hsl(240 10% 3.9%)',
            foreground: 'hsl(0 0% 98%)',
            primary: { DEFAULT: 'hsl(0 0% 98%)', foreground: 'hsl(240 5.9% 10%)' },
            secondary: { DEFAULT: 'hsl(240 3.7% 15.9%)', foreground: 'hsl(0 0% 98%)' },
            muted: { DEFAULT: 'hsl(240 3.7% 15.9%)', foreground: 'hsl(240 5% 64.9%)' },
            accent: { DEFAULT: 'hsl(240 3.7% 15.9%)', foreground: 'hsl(0 0% 98%)' },
            card: { DEFAULT: 'hsl(240 10% 3.9%)', foreground: 'hsl(0 0% 98%)' },
            popover: { DEFAULT: 'hsl(240 10% 3.9%)', foreground: 'hsl(0 0% 98%)' },
          },
          fontFamily: {
            sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
            mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
          },
          keyframes: {
            'fade-in': { '0%': { opacity: '0', transform: 'translateY(20px)' }, '100%': { opacity: '1', transform: 'translateY(0)' } },
            'fade-in-slow': { '0%': { opacity: '0', transform: 'translateY(40px)' }, '100%': { opacity: '1', transform: 'translateY(0)' } },
            'pulse-glow': { '0%, 100%': { boxShadow: '0 0 20px rgba(99, 102, 241, 0.3)' }, '50%': { boxShadow: '0 0 40px rgba(99, 102, 241, 0.6)' } },
            'gradient-shift': { '0%': { backgroundPosition: '0% 50%' }, '50%': { backgroundPosition: '100% 50%' }, '100%': { backgroundPosition: '0% 50%' } },
            'float': { '0%, 100%': { transform: 'translateY(0px)' }, '50%': { transform: 'translateY(-10px)' } },
            'slide-in-left': { '0%': { opacity: '0', transform: 'translateX(-30px)' }, '100%': { opacity: '1', transform: 'translateX(0)' } },
            'slide-in-right': { '0%': { opacity: '0', transform: 'translateX(30px)' }, '100%': { opacity: '1', transform: 'translateX(0)' } },
            'scale-in': { '0%': { opacity: '0', transform: 'scale(0.95)' }, '100%': { opacity: '1', transform: 'scale(1)' } },
          },
          animation: {
            'fade-in': 'fade-in 0.6s ease-out forwards',
            'fade-in-slow': 'fade-in-slow 0.8s ease-out forwards',
            'pulse-glow': 'pulse-glow 3s ease-in-out infinite',
            'gradient-shift': 'gradient-shift 8s ease infinite',
            'float': 'float 6s ease-in-out infinite',
            'slide-in-left': 'slide-in-left 0.6s ease-out forwards',
            'slide-in-right': 'slide-in-right 0.6s ease-out forwards',
            'scale-in': 'scale-in 0.5s ease-out forwards',
          },
        },
      },
    };
