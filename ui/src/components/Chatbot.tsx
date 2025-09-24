import React, {useState} from 'react';
import './Chatbot.css';
import { PageState } from '../pages/Home';
import type { PageStateType } from '../pages/Home';

interface ChatbotProps {
  setPageState: (state: PageStateType) => void;
}

const Chatbot: React.FC<ChatbotProps> = ({setPageState}) => {
    const [isOpen, setIsOpen] = useState(false);

    const backToLogin = () => {
        setPageState(PageState.LOGIN);
    }

    const toggleChatbot = () => {
        setIsOpen(!isOpen);
        console.log("Chatbot Button Pressed");
    };

    return (
        <>
            <h1>Chatbot Component Goes Here</h1>
            <button onClick={toggleChatbot}>Talk to Chatbot</button>
            <button onClick={backToLogin}>Back to Login</button>
        </>
    )

};

export default Chatbot;
