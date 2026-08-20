import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import './index.css';
import { applyPerspective, useStore } from './lib/store';

applyPerspective(useStore.getState().perspective);
useStore.subscribe((state, prev) => {
  if (state.perspective !== prev.perspective) applyPerspective(state.perspective);
});

void useStore.getState().load();

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
