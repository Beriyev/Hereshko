from fastapi import APIRouter, HTTPException
from app.services.testweaver.generator import generate_subjective_test, generate_mcq_test, subjective_compare_answers
from app.schemas.testweaver import Question, MCQQuestion, Result

router = APIRouter()

@router.post("/testweaver/subjective/generate")
async def subjective_generation(document_id: str, notebook_id: str, number_of_questions: int) -> list[tuple[Question,str]]:
    if number_of_questions < 1 or number_of_questions > 3:
        raise HTTPException(422,"Subjective tests must contain between 1 and 3 questions.")
    question_answer_pairs = await generate_subjective_test(document_id=document_id,notebook_id=notebook_id,number_of_questions=number_of_questions)
    return question_answer_pairs

@router.post("/testweaver/objective/generate")
async def objective_generation(document_id: str, notebook_id: str, number_of_questions: int) -> list[MCQQuestion]:
    if number_of_questions < 1 or number_of_questions > 10:
        raise HTTPException(422,"Objective tests must contain between 1 and 10 questions.")
    mcq_questions = await generate_mcq_test(document_id=document_id,notebook_id=notebook_id,number_of_questions=number_of_questions)
    return mcq_questions

@router.post("/testweaver/subjective/submit")
async def compare_subjective(pairs_list: list[tuple[Question,str]], answer_list: list[str]) -> list[Result]:
    if len(pairs_list) != len(answer_list):
        raise HTTPException(422,"Each question must have an answer.")
    results: list[Result] = []
    for pair,answer in zip(pairs_list,answer_list):
        results.append(await subjective_compare_answers(question=pair[0].question,expected_answer=pair[1],provided_answer=answer))
    return results

@router.post("/testweaver/objective/submit")
async def compare_objective(question_list: list[MCQQuestion], provided_answers_list: list[str]) -> list[Result]:
    if len(question_list) != len(provided_answers_list):
        raise HTTPException(422,"Each question must have an answer.")
    results: list[Result] = []
    for question_module,answer in zip(question_list,provided_answers_list):
        if answer==question_module.correct_option:
            results.append(Result(correctness='correct',score=10,mcq_explanation=question_module.explanation))
        else:
            results.append(Result(correctness='incorrect',score=0,mcq_explanation=question_module.explanation))
    return results
                       
